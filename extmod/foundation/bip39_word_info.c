// SPDX-FileCopyrightText: © 2021 Foundation Devices, Inc. <hello@foundationdevices.com>
// SPDX-License-Identifier: GPL-3.0-or-later
//

#include <stdint.h>

typedef struct {
    uint32_t keypad_digits;
    uint16_t offsets;
} word_info_t;

word_info_t bip39_word_info[] = {
    {224, 0x4000},       // bag
    {226, 0x8400}
};
