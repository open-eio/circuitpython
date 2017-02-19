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

#include "py/objproperty.h"
#include "py/runtime.h"
#include "shared-bindings/microcontroller/Pin.h"
#include "shared-bindings/nativeio/PWMOut.h"

//| .. currentmodule:: nativeio
//|
//| :class:`PWMOut` -- Output a Pulse Width Modulated signal
//| ========================================================
//|
//| PWMOut can be used to output a PWM signal on a given pin.
//|
//| .. class:: PWMOut(pin, duty_cycle=0, frequency=500, variable_frequency=False)
//|
//|   Create a PWM object associated with the given pin. This allows you to
//|   write PWM signals out on the given pin. Frequency is fixed after init
//|   unless `variable_frequency` is True.
//|
//|   .. note:: When ``variable_frequency`` is True, further PWM outputs may be
//|     limited because it may take more internal resources to be flexible. So,
//|     when outputting both fixed and flexible frequency signals construct the
//|     fixed outputs first.
//|
//|   :param ~microcontroller.Pin pin: The pin to output to
//|   :param int duty: The fraction of each pulse which is high. 16-bit
//|   :param int frequency: The target frequency in Hertz (32-bit)
//|   :param bool variable_frequency: True if the frequency will change over time
//|
//|   Simple LED fade::
//|
//|     import nativeio
//|     import board
//|
//|     with nativeio.PWMOut(board.D13) as pwm:     # output on D13
//|       pwm.duty_cycle = 2 ** 15                  # Cycles the pin with 50% duty cycle (half of 2 ** 16) at the default 500hz
//|
//|   PWM at specific frequency (servos and motors)::
//|
//|     import nativeio
//|     import board
//|
//|     with nativeio.PWMOut(board.D13, frequency=50) as pwm:
//|       pwm.duty_cycle = 2 ** 15                  # Cycles the pin with 50% duty cycle (half of 2 ** 16) at 50hz
//|
//|   Variable frequency (usually tones)::
//|
//|     import nativeio
//|     import board
//|     import time
//|
//|     with nativeio.PWMOut(board.D13, duty_cycle=2 ** 15, frequency=440, variable_frequency=True) as pwm:
//|       time.sleep(0.2)
//|       pwm.frequency = 880
//|       time.sleep(0.1)
//|
STATIC mp_obj_t nativeio_pwmout_make_new(const mp_obj_type_t *type, size_t n_args, size_t n_kw, const mp_obj_t *args) {
    mp_arg_check_num(n_args, n_kw, 1, MP_OBJ_FUN_ARGS_MAX, true);
    mp_obj_t pin_obj = args[0];
    assert_pin(pin_obj, false);
    const mcu_pin_obj_t *pin = MP_OBJ_TO_PTR(pin_obj);
    assert_pin_free(pin);

    // create PWM object from the given pin
    nativeio_pwmout_obj_t *self = m_new_obj(nativeio_pwmout_obj_t);
    self->base.type = &nativeio_pwmout_type;

    mp_map_t kw_args;
    mp_map_init_fixed_table(&kw_args, n_kw, args + n_args);
    enum { ARG_duty, ARG_frequency, ARG_variable_frequency };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_duty_cycle, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_frequency, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 500} },
        { MP_QSTR_variable_frequency, MP_ARG_KW_ONLY | MP_ARG_BOOL, {.u_bool = false} },
    };
    mp_arg_val_t parsed_args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args - 1, args + 1, &kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, parsed_args);
    uint8_t duty = parsed_args[ARG_duty].u_int;
    uint32_t frequency = parsed_args[ARG_frequency].u_int;
    bool variable_frequency = parsed_args[ARG_variable_frequency].u_int;

    common_hal_nativeio_pwmout_construct(self, pin, duty, frequency, variable_frequency);

    return MP_OBJ_FROM_PTR(self);
}

//|   .. method:: deinit()
//|
//|      Deinitialises the PWMOut and releases any hardware resources for reuse.
//|
STATIC mp_obj_t nativeio_pwmout_deinit(mp_obj_t self_in) {
    nativeio_pwmout_obj_t *self = MP_OBJ_TO_PTR(self_in);
    common_hal_nativeio_pwmout_deinit(self);
    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(nativeio_pwmout_deinit_obj, nativeio_pwmout_deinit);

//|   .. method:: __enter__()
//|
//|      No-op used by Context Managers.
//|
STATIC mp_obj_t nativeio_pwmout_obj___enter__(mp_obj_t self_in) {
   return self_in;
}
MP_DEFINE_CONST_FUN_OBJ_1(nativeio_pwmout___enter___obj, nativeio_pwmout_obj___enter__);

//|   .. method:: __exit__()
//|
//|      Automatically deinitializes the hardware when exiting a context.
//|
STATIC mp_obj_t nativeio_pwmout_obj___exit__(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    common_hal_nativeio_pwmout_deinit(args[0]);
    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(nativeio_pwmout___exit___obj, 4, 4, nativeio_pwmout_obj___exit__);

//|   .. attribute:: duty_cycle
//|
//|      16 bit value that dictates how much of one cycle is high (1) versus low
//|      (0). 255 will always be high, 0 will always be low and 127 will be half
//|      high and then half low.
STATIC mp_obj_t nativeio_pwmout_obj_get_duty_cycle(mp_obj_t self_in) {
   nativeio_pwmout_obj_t *self = MP_OBJ_TO_PTR(self_in);
   return MP_OBJ_NEW_SMALL_INT(common_hal_nativeio_pwmout_get_duty_cycle(self));
}
MP_DEFINE_CONST_FUN_OBJ_1(nativeio_pwmout_get_duty_cycle_obj, nativeio_pwmout_obj_get_duty_cycle);

STATIC mp_obj_t nativeio_pwmout_obj_set_duty_cycle(mp_obj_t self_in, mp_obj_t duty_cycle) {
    nativeio_pwmout_obj_t *self = MP_OBJ_TO_PTR(self_in);
    mp_int_t duty = mp_obj_get_int(duty_cycle);
    if (duty < 0 || duty > 0xffff) {
        nlr_raise(mp_obj_new_exception_msg_varg(&mp_type_ValueError,
            "PWM duty must be between 0 and 65536 (16 bit resolution), not %d",
            duty));
    }
   common_hal_nativeio_pwmout_set_duty_cycle(self, duty);
   return mp_const_none;
}
MP_DEFINE_CONST_FUN_OBJ_2(nativeio_pwmout_set_duty_cycle_obj, nativeio_pwmout_obj_set_duty_cycle);

mp_obj_property_t nativeio_pwmout_duty_cycle_obj = {
    .base.type = &mp_type_property,
    .proxy = {(mp_obj_t)&nativeio_pwmout_get_duty_cycle_obj,
              (mp_obj_t)&nativeio_pwmout_set_duty_cycle_obj,
              (mp_obj_t)&mp_const_none_obj},
};

//|   .. attribute:: frequency
//|
//|     32 bit value that dictates the PWM frequency in Hertz (cycles per
//|     second). Only writeable when constructed with ``variable_frequency=True``.
//|
STATIC mp_obj_t nativeio_pwmout_obj_get_frequency(mp_obj_t self_in) {
   nativeio_pwmout_obj_t *self = MP_OBJ_TO_PTR(self_in);
   return MP_OBJ_NEW_SMALL_INT(common_hal_nativeio_pwmout_get_frequency(self));
}
MP_DEFINE_CONST_FUN_OBJ_1(nativeio_pwmout_get_frequency_obj, nativeio_pwmout_obj_get_frequency);

STATIC mp_obj_t nativeio_pwmout_obj_set_frequency(mp_obj_t self_in, mp_obj_t frequency) {
    nativeio_pwmout_obj_t *self = MP_OBJ_TO_PTR(self_in);
    if (!common_hal_nativeio_pwmout_get_variable_frequency(self)) {
        nlr_raise(mp_obj_new_exception_msg_varg(&mp_type_AttributeError,
            "PWM frequency not writeable when variable_frequency is False on "
            "construction."));
    }
   common_hal_nativeio_pwmout_set_frequency(self, mp_obj_get_int(frequency));
   return mp_const_none;
}
MP_DEFINE_CONST_FUN_OBJ_2(nativeio_pwmout_set_frequency_obj, nativeio_pwmout_obj_set_frequency);

mp_obj_property_t nativeio_pwmout_frequency_obj = {
    .base.type = &mp_type_property,
    .proxy = {(mp_obj_t)&nativeio_pwmout_get_frequency_obj,
              (mp_obj_t)&nativeio_pwmout_set_frequency_obj,
              (mp_obj_t)&mp_const_none_obj},
};

STATIC const mp_rom_map_elem_t nativeio_pwmout_locals_dict_table[] = {
    // Methods
    { MP_ROM_QSTR(MP_QSTR_deinit), MP_ROM_PTR(&nativeio_pwmout_deinit_obj) },
    { MP_ROM_QSTR(MP_QSTR___enter__), MP_ROM_PTR(&nativeio_pwmout___enter___obj) },
    { MP_ROM_QSTR(MP_QSTR___exit__), MP_ROM_PTR(&nativeio_pwmout___exit___obj) },

    // Properties
    { MP_ROM_QSTR(MP_QSTR_duty_cycle), MP_ROM_PTR(&nativeio_pwmout_duty_cycle_obj) },
    { MP_ROM_QSTR(MP_QSTR_frequency), MP_ROM_PTR(&nativeio_pwmout_frequency_obj) },
    // TODO(tannewt): Add enabled to determine whether the signal is output
    // without giving up the resources. Useful for IR output.
};
STATIC MP_DEFINE_CONST_DICT(nativeio_pwmout_locals_dict, nativeio_pwmout_locals_dict_table);

const mp_obj_type_t nativeio_pwmout_type = {
    { &mp_type_type },
    .name = MP_QSTR_PWMOut,
    .make_new = nativeio_pwmout_make_new,
    .locals_dict = (mp_obj_dict_t*)&nativeio_pwmout_locals_dict,
};
