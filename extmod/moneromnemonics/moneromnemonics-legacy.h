#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "py/runtime.h"
#include "py/objstr.h"
#include "py/objint.h"

#include "legacy_monero_mnemonic.h"

/// package: moneromnemoncs

/// def from_seed(seed: bytes, language: int) -> str:
///     """
///     Generate a mnemonic from given 32 bytes of data.
///     """
STATIC mp_obj_t moneromnemonics_legacy_from_seed(size_t n_args,
                                            const mp_obj_t *args) {
  mp_buffer_info_t bin = {0};
  mp_uint_t in_language = 0;
  mp_get_buffer_raise(args[0], &bin, MP_BUFFER_READ);
  if (n_args >= 2)
    in_language = mp_obj_int_get_uint_checked(args[1]);
  if (bin.len % 4 || bin.len < 16 || bin.len > 32) {
    mp_raise_ValueError(
      MP_ERROR_TEXT("Invalid data length (only 16, 20, 24, 28 and 32 bytes are allowed)"));
  }
  enum MoneroLanguage language = MoneroLanguageNone;
  if (in_language <= 0) {
    language = MoneroEnglish;
  } else {
    language = in_language;
  }
  const char *mnemonic = legacy_monero_mnemonic_from_seed(bin.buf, bin.len, language);
  mp_obj_t res = mnemonic ? mp_obj_new_str_copy(&mp_type_str, (const uint8_t *)mnemonic, strlen(mnemonic)) : mp_obj_new_str("", 0);
  clear_legacy_monero_mnemonic();
  return res;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(moneromnemonics_legacy_from_seed_obj, 1,
                                 2, moneromnemonics_legacy_from_seed);

/// def check(mnemonic: str) -> bool:
///     """
///     Check whether given mnemonic is valid.
///     """
STATIC mp_obj_t moneromnemonics_legacy_check(mp_obj_t mnemonic, mp_obj_t language_obj) {
  mp_buffer_info_t text = {0};
  mp_uint_t in_language = mp_obj_int_get_uint_checked(language_obj);
  mp_get_buffer_raise(mnemonic, &text, MP_BUFFER_READ);
  enum MoneroLanguage language = MoneroLanguageNone;
  if (in_language <= 0) {
    language = MoneroEnglish;
  } else {
    language = in_language;
  }
  return (text.len > 0 && legacy_monero_mnemonic_check(text.buf, language)) ? mp_const_true : mp_const_false;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_2(moneromnemonics_legacy_check_obj,
                                 moneromnemonics_legacy_check);

/// def to_seed(mnemonic: str, language: int) -> bytes:
///     """
///     Generate seed from mnemonic.
///     """
STATIC mp_obj_t moneromnemonics_legacy_to_seed(mp_obj_t mnemonic, mp_obj_t language_obj) {
  mp_buffer_info_t mnemonic_obj = {0};
  mp_uint_t in_language = mp_obj_int_get_uint_checked(language_obj);
  mp_get_buffer_raise(mnemonic, &mnemonic_obj, MP_BUFFER_READ);
  vstr_t seed = {0};
  vstr_init_len(&seed, MONERO_SEED_BITS/8);
  const char *pmnemonic = mnemonic_obj.len > 0 ? mnemonic_obj.buf : "";
  enum MoneroLanguage language = MoneroLanguageNone;
  if (in_language <= 0) {
    language = MoneroEnglish;
  } else {
    language = in_language;
  }
  legacy_monero_mnemonic_to_seed(pmnemonic, (uint8_t *)seed.buf, language);
  return mp_obj_new_str_from_vstr(&mp_type_bytes, &seed);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_2(moneromnemonics_legacy_to_seed_obj,
                                           moneromnemonics_legacy_to_seed);


STATIC const mp_rom_map_elem_t moneromnemonics_legacy_globals_table[] = {
    {MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_legacy)},
    {MP_ROM_QSTR(MP_QSTR_from_seed), MP_ROM_PTR(&moneromnemonics_legacy_from_seed_obj)},
    {MP_ROM_QSTR(MP_QSTR_check), MP_ROM_PTR(&moneromnemonics_legacy_check_obj)},
    {MP_ROM_QSTR(MP_QSTR_to_seed), MP_ROM_PTR(&moneromnemonics_legacy_to_seed_obj)}
};
STATIC MP_DEFINE_CONST_DICT(moneromnemonics_legacy_globals, moneromnemonics_legacy_globals_table);

STATIC const mp_obj_module_t moneromnemonics_legacy_module = {
    .base = {&mp_type_module},
    .globals = (mp_obj_dict_t *)&moneromnemonics_legacy_globals,
};
