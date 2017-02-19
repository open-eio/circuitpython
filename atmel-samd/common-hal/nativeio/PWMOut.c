/*
 * This file is part of the Micro Python project, http://micropython.org/
 *
 * The MIT License (MIT)
 *
 * Copyright (c) 2016 Damien P. George
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

#include <stdint.h>

#include "py/runtime.h"
#include "common-hal/nativeio/PWMOut.h"
#include "shared-bindings/nativeio/PWMOut.h"

#include "samd21_pins.h"

#undef ENABLE

uint32_t target_timer_frequencies[TC_INST_NUM + TCC_INST_NUM];
uint8_t timer_refcount[TC_INST_NUM + TCC_INST_NUM];
const uint16_t prescaler[8] = {1, 2, 4, 8, 16, 64, 256, 1024};

// This bitmask keeps track of which channels of a TCC are currently claimed.
uint8_t tcc_channels[3] = {0xf0, 0xfc, 0xfc};

void pwmout_reset(void) {
    // Reset all but TC5
    for (int i = 0; i < TC_INST_NUM + TCC_INST_NUM; i++) {
        if (i == 5) {
            target_timer_frequencies[i] = 1000;
            timer_refcount[i] = 1;
        } else {
            target_timer_frequencies[i] = 0;
            timer_refcount[i] = 0;
        }
    }
    Tcc *tccs[TCC_INST_NUM] = TCC_INSTS;
    for (int i = 0; i < TCC_INST_NUM; i++) {
        tccs[i]->CTRLA.bit.SWRST = 1;
    }
    Tc *tcs[TC_INST_NUM] = TC_INSTS;
    for (int i = 0; i < TC_INST_NUM; i++) {
        if (tcs[i] == TC5) {
            continue;
        }
        tcs[i]->COUNT16.CTRLA.bit.SWRST = 1;
    }
}

bool channel_ok(const pin_timer_t* t, uint8_t index) {
    return (!t->is_tc && (tcc_channels[index] & (1 << t->channel)) == 0) ||
            t->is_tc;
}

void common_hal_nativeio_pwmout_construct(nativeio_pwmout_obj_t* self,
                                          const mcu_pin_obj_t* pin,
                                          uint16_t duty,
                                          uint32_t frequency,
                                          bool variable_frequency) {
    self->pin = pin;
    self->variable_frequency = variable_frequency;

    if (pin->primary_timer.tc == 0 && pin->secondary_timer.tc == 0) {
        nlr_raise(mp_obj_new_exception_msg_varg(&mp_type_ValueError,
            "Invalid pin."));
    }

    if (frequency == 0 || frequency > 6000000) {
        nlr_raise(mp_obj_new_exception_msg_varg(&mp_type_ValueError,
            "Invalid PWM frequency."));
    }

    uint16_t primary_timer_index = 0xff;
    uint16_t secondary_timer_index = 0xff;
    if (pin->primary_timer.tc != NULL) {
        primary_timer_index = (((uint32_t) pin->primary_timer.tcc) - ((uint32_t) TCC0)) / 0x400;
    }
    if (pin->secondary_timer.tc != NULL) {
        secondary_timer_index = (((uint32_t) pin->secondary_timer.tcc) - ((uint32_t) TCC0)) / 0x400;
    }

    // Figure out which timer we are using.

    // First see if a timer is already going with the frequency we want and our
    // channel is unused.
    // NOTE(shawcroft): The enable bit is in the same position for TC and TCC so
    // we treat them all as TCC for checking ENABLE.
    const pin_timer_t* t = NULL;
    uint8_t index = 0;
    if (!variable_frequency &&
        primary_timer_index != 0xff &&
        target_timer_frequencies[primary_timer_index] == frequency &&
        pin->primary_timer.tcc->CTRLA.bit.ENABLE == 1 &&
        channel_ok(&pin->primary_timer, primary_timer_index)) {
        t = &pin->primary_timer;
        index = primary_timer_index;
    } else if (!variable_frequency &&
               secondary_timer_index != 0xff &&
               target_timer_frequencies[secondary_timer_index] == frequency &&
               pin->secondary_timer.tcc->CTRLA.bit.ENABLE == 1 &&
               channel_ok(&pin->secondary_timer, secondary_timer_index)) {
        t = &pin->secondary_timer;
        index = secondary_timer_index;
    } else {
        // Pick an unused timer if available.

        // Check the secondary timer first since its always a nicer TCC (when it
        // exists)
        if (pin->secondary_timer.tc != 0 &&
            timer_refcount[secondary_timer_index] == 0 &&
            pin->secondary_timer.tcc->CTRLA.bit.ENABLE == 0) {
            t = &pin->secondary_timer;
            index = secondary_timer_index;
        } else if (pin->primary_timer.tc != 0 &&
                   (!pin->primary_timer.is_tc || pin->primary_timer.channel == 1) &&
                   timer_refcount[primary_timer_index] == 0) {
            t = &pin->primary_timer;
            index = primary_timer_index;
        }
        if (t == NULL) {
            nlr_raise(mp_obj_new_exception_msg(&mp_type_OSError, "All timers in use."));
            return;
        }
        uint8_t resolution = 0;
        if (t->is_tc) {
            resolution = 16;
        } else {
            resolution = 24;
        }
        // First determine the divisor that gets us the highest resolution.
        uint32_t system_clock = system_cpu_clock_get_hz();
        uint32_t top;
        uint8_t divisor;
        for (divisor = 0; divisor < 8; divisor++) {
            top = (system_clock / prescaler[divisor] / frequency) - 1;
            if (top < (1u << resolution)) {
                break;
            }
        }
        if (t->is_tc) {
            struct tc_config config_tc;
            tc_get_config_defaults(&config_tc);

            config_tc.counter_size    = TC_COUNTER_SIZE_16BIT;
            config_tc.clock_prescaler = TC_CTRLA_PRESCALER(divisor);
            config_tc.wave_generation = TC_WAVE_GENERATION_MATCH_PWM;
            config_tc.counter_16_bit.compare_capture_channel[0] = top;

            tc_init(&self->tc_instance, t->tc, &config_tc);
            tc_enable(&self->tc_instance);
        } else {
            struct tcc_config config_tcc;
            tcc_get_config_defaults(&config_tcc, t->tcc);

            config_tcc.counter.clock_prescaler = divisor;
            config_tcc.counter.period = top;
            config_tcc.compare.wave_generation = TCC_WAVE_GENERATION_SINGLE_SLOPE_PWM;

            tcc_init(&self->tcc_instance, t->tcc, &config_tcc);
            tcc_enable(&self->tcc_instance);
        }

        target_timer_frequencies[index] = frequency;
        timer_refcount[index]++;
    }

    if (!t->is_tc) {
        if (variable_frequency) {
            // We're changing frequency so claim all of the channels.
            tcc_channels[index] = 0xff;
        } else {
            tcc_channels[index] |= (1 << t->channel);
        }
    }

    self->timer = t;

    // Connect the wave output to the outside world.
    struct system_pinmux_config pin_config;
    system_pinmux_get_config_defaults(&pin_config);
    pin_config.mux_position = &self->pin->primary_timer == t ? MUX_E : MUX_F;
    pin_config.direction = SYSTEM_PINMUX_PIN_DIR_OUTPUT;
    system_pinmux_pin_set_config(pin->pin, &pin_config);

    common_hal_nativeio_pwmout_set_duty_cycle(self, duty);
}

extern void common_hal_nativeio_pwmout_deinit(nativeio_pwmout_obj_t* self) {
    const pin_timer_t* t = self->timer;
    uint8_t index = (((uint32_t) t->tcc) - ((uint32_t) TCC0)) / 0x400;
    timer_refcount[index]--;
    if (!t->is_tc) {
        tcc_channels[index] &= ~(1 << t->channel);
    }
    if (timer_refcount[index] == 0) {
        target_timer_frequencies[index] = 0;
        if (t->is_tc) {
            tc_disable(&self->tc_instance);
        } else {
            if (t->tcc == TCC0) {
                tcc_channels[index] = 0xf0;
            } else {
                tcc_channels[index] = 0xfc;
            }
            tcc_disable(&self->tcc_instance);
            tcc_reset(&self->tcc_instance);
        }
    }
    reset_pin(self->pin->pin);
}

extern void common_hal_nativeio_pwmout_set_duty_cycle(nativeio_pwmout_obj_t* self, uint16_t duty) {
    const pin_timer_t* t = self->timer;
    if (t->is_tc) {
        uint32_t top = ((uint32_t) t->tc->COUNT16.CC[0].reg + 1);
        uint16_t adjusted_duty = top * duty / 0xffff;
        tc_set_compare_value(&self->tc_instance, t->channel, adjusted_duty);
    } else {
        uint32_t top = t->tcc->PER.reg + 1;
        uint32_t adjusted_duty = ((uint64_t) top) * duty / 0xffff;
        tcc_set_compare_value(&self->tcc_instance, t->channel, adjusted_duty);
    }
}

uint16_t common_hal_nativeio_pwmout_get_duty_cycle(nativeio_pwmout_obj_t* self) {
    const pin_timer_t* t = self->timer;
    if (t->is_tc) {
        uint16_t top = t->tc->COUNT16.CC[0].reg;
        while (tc_is_syncing(&self->tc_instance)) {
            /* Wait for sync */
        }
        uint16_t cv = t->tc->COUNT16.CC[t->channel].reg;
        return cv * 0xffff / top;
    } else {
        uint32_t top = t->tcc->PER.reg;
        uint32_t cv = 0;
        if ((t->tcc->STATUS.vec.CCBV & (1 << t->channel)) != 0) {
            cv = t->tcc->CCB[t->channel].reg;
        } else {
            cv = t->tcc->CC[t->channel].reg;
        }
        return cv * 0xffff / top;
    }
}


void common_hal_nativeio_pwmout_set_frequency(nativeio_pwmout_obj_t* self,
                                              uint32_t frequency) {
    if (frequency == 0 || frequency > 6000000) {
        nlr_raise(mp_obj_new_exception_msg_varg(&mp_type_ValueError,
            "Invalid PWM frequency."));
    }
    const pin_timer_t* t = self->timer;
    uint8_t resolution;
    if (t->is_tc) {
        resolution = 16;
    } else {
        resolution = 24;
    }
    uint32_t system_clock = system_cpu_clock_get_hz();
    uint32_t new_top;
    uint8_t new_divisor;
    for (new_divisor = 0; new_divisor < 8; new_divisor++) {
        new_top = (system_clock / prescaler[new_divisor] / frequency) - 1;
        if (new_top < (1u << resolution)) {
            break;
        }
    }
    uint16_t old_duty = common_hal_nativeio_pwmout_get_duty_cycle(self);
    uint8_t old_divisor;
    if (t->is_tc) {
        old_divisor = t->tc->COUNT16.CTRLA.bit.PRESCALER;
    } else {
        old_divisor = t->tcc->CTRLA.bit.PRESCALER;
    }
    if (new_divisor != old_divisor) {
        if (t->is_tc) {
            tc_disable(&self->tc_instance);
            t->tc->COUNT16.CTRLA.bit.PRESCALER = new_divisor;
            tc_enable(&self->tc_instance);
        } else {
            tcc_disable(&self->tcc_instance);
            t->tcc->CTRLA.bit.PRESCALER = new_divisor;
            tcc_enable(&self->tcc_instance);
        }
    }
    if (t->is_tc) {
        while (tc_is_syncing(&self->tc_instance)) {
            /* Wait for sync */
        }
        t->tc->COUNT16.CC[0].reg = new_top;
    } else {
        tcc_set_top_value(&self->tcc_instance, new_top);
    }

    common_hal_nativeio_pwmout_set_duty_cycle(self, old_duty);
}

uint32_t common_hal_nativeio_pwmout_get_frequency(nativeio_pwmout_obj_t* self) {
    uint32_t system_clock = system_cpu_clock_get_hz();
    const pin_timer_t* t = self->timer;
    uint32_t top;
    uint8_t divisor;
    if (t->is_tc) {
        top = t->tc->COUNT16.CC[0].reg;
        divisor = t->tc->COUNT16.CTRLA.bit.PRESCALER;
    } else {
        top = t->tcc->PER.reg;
        divisor = t->tcc->CTRLA.bit.PRESCALER;
    }
    return (system_clock / prescaler[divisor]) / (top + 1);
}

bool common_hal_nativeio_pwmout_get_variable_frequency(nativeio_pwmout_obj_t* self) {
    return self->variable_frequency;
}
