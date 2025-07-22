

#include "py/obj.h"
#include "py/objstr.h"
#include "py/stream.h"
#include "py/runtime.h"

#include "moneromnemonics-legacy.h"

/// package: moneromnemonics

/* Module Global configuration */
/* Define all properties of the module.
 * Table entries are key/value pairs of the attribute name (a string)
 * and the MicroPython object reference.
 * All identifiers and strings are written as MP_QSTR_xxx and will be
 * optimized to word-sized integers by the build system (interned strings).
 */

STATIC const mp_rom_map_elem_t moneromnemonics_globals_table[] = {
    {MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_moneromnemonics)},
    {MP_ROM_QSTR(MP_QSTR_legacy), MP_ROM_PTR(&moneromnemonics_legacy_module)}
};
STATIC MP_DEFINE_CONST_DICT(moneromnemonics_globals, moneromnemonics_globals_table);

/* Define module object. */
const mp_obj_module_t moneromnemonics_module = {
    .base = {&mp_type_module},
    .globals = (mp_obj_dict_t *)&moneromnemonics_globals,
};

MP_REGISTER_MODULE(MP_QSTR_moneromnemonics, moneromnemonics_module, 1);
