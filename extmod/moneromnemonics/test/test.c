#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "legacy_monero_mnemonic.h"
#include "monero_english_words.h"

size_t char_to_uint8(uint8_t* dest, size_t count, const char* src) {
    size_t i;
    int value;
    for (i=0;i<count && sscanf(src + i * 2, "%2x", &value) == 1;i++) {
        dest[i] = value;
    }
    return i; 
}

uint8_t uint8_to_char(char* dest, size_t dest_len, const uint8_t* src, size_t src_len) {
    if (dest_len < (src_len*2+1)) return 0;
    *dest = '\0';
    while(src_len--) {
        sprintf(dest, "%02X", *src);
        dest += 2;
        ++src;
    }
    return 1;
}

int test_seed(char* seed_str, char* mc) {
    uint8_t seed[32] = { 0 };
    char_to_uint8(seed, 64, seed_str);
    const char* mnemonic = legacy_monero_mnemonic_from_seed(seed, 32, MoneroEnglish);
    strcpy(mc, mnemonic);
    clear_legacy_monero_mnemonic();
    int32_t check_result = legacy_monero_mnemonic_check(mc, MoneroEnglish);
    //printf("%s => [%02X %02X %02X ... %02X %02X %02X]=> '%s', check: %i\n", seed_str, seed[0], seed[1], seed[2], seed[29], seed[30], seed[31], mc, check_result);
    return check_result;
}

int test_mnemonic(char* mnemonic, char* seed_str) {
    uint8_t seed[32] = { 0 };
    uint8_t success = legacy_monero_mnemonic_to_seed(mnemonic, seed, MoneroEnglish);
    uint8_to_char(seed_str, 65, seed, 32);
    return success;
}

char* uppercase(char* input) {
    char* in = input;
    while (*in != '\0') {
        if (*in >= 0x61 && *in <= (0x61+27)) *in = *in - 0x20;
        in++;
    }
    return input;
}

int main(int argc, char** argv) {
    if (argc > 1) {
        if (strcmp(argv[1], "seed") == 0 || strcmp(argv[1], "s") == 0) {
            char mnemonic[MONERO_MNEMONIC_MAXIMUM_LENGTH] = { '\0' };
            int result = test_seed(argv[2], mnemonic);
            printf("%s => '%s', check: %i\n", argv[2], mnemonic, result);
            return result;
        } else if (strcmp(argv[1], "mnemonic") == 0 || strcmp(argv[1], "m") == 0) {
            char mnemonic[2*MONERO_MNEMONIC_MAXIMUM_LENGTH] = { '\0' };
            for (int i = 2; i < argc; i++) {
                strcat(mnemonic, argv[i]);
                if (i < argc-1) {
                    strcat(mnemonic, " ");
                }
            }
            printf("Using mnemonic: '%s'\n", mnemonic);
            char seed_str[65] = { '\0' };
            int result = test_mnemonic(mnemonic, seed_str);
            printf("'%s' => %s, success: %i\n", mnemonic, seed_str, result);
            return result;
        } else {
            printf("Usage: test [seed|mnemonic]\n");
        }
    }

    printf("Checking that all words in english word list can have their index be found.\n\n");
    for (int i = 0; i < MONERO_WORDLIST_WORD_COUNT; i++) {
        int ind = monero_mnemonic_find_word_index(monero_english_words[i], MoneroEnglish);
        if (ind != i) {
            printf("Mismatch between (%i, %i).\n", ind, i);
            return 1;
        }
    }
    char* valid_seeds[] = {
        "a4f9f927ea309d35ecf6a149b3e32cad54d6f769b93eab05311f77472231080f",
        "EC050000EC050000EC050000EC050000EC050000EC050000EC050000EC050000"
        };
    for (int i = 0; i < sizeof(valid_seeds)/sizeof(char*); i++) {
        char mnemonic[MONERO_MNEMONIC_MAXIMUM_LENGTH];
        if (!test_seed(valid_seeds[i], mnemonic)) {
            printf("Failed to generate mnemonic from seed '%s'.\n", valid_seeds[i]);
            return 1;
        }
        printf("Generated mnemonic '%s' from seed '%s'.\n\n", mnemonic, valid_seeds[i]);
        char seed_str[65] = { '\0' };
        if (!test_mnemonic(mnemonic, seed_str)) {
            printf("Failed to generate seed from mnemonic '%s'.\n", mnemonic);
            return 1;
        }
        printf("Generated seed '%s' from mnemonic '%s'.\n\n", seed_str, mnemonic);
        char* cpy = malloc(strlen(valid_seeds[i])+1);
        strcpy(cpy, valid_seeds[i]);
        if (strcmp(uppercase(cpy), uppercase(seed_str)) != 0) {
            free(cpy);
            printf("Seed mismatch between %s and %s.\n", valid_seeds[i], seed_str);
            return 1;
        }
        free(cpy);
        printf("Original seed '%s' and regenerated seed '%s' match.\n\n", valid_seeds[i], seed_str);
    }
    char* valid_mnemonics[] = {
        "stacking lexicon payment input paddles tequila oxygen tutor cuffs affair vials ongoing pelican badge logic lilac kitchens lexicon portents cuisine jolted moment vegan yellow cuisine",
        //longest possible mnemonic
        "verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification",
        //no checksum word
        "abbey abducts ability ablaze abnormal abort abrasive absorb abyss academy aces aching acidic acoustic acquire across actress acumen adapt addicted adept adhesive adjust adopt"
        };
    for (int i = 0; i < sizeof(valid_mnemonics)/sizeof(char*); i++) {
        char seed_str[65] = { '\0' };
        if (!test_mnemonic(valid_mnemonics[i], seed_str)) {
            printf("Failed to generate seed from mnemonic '%s'.\n", valid_mnemonics[i]);
            return 1;
        }
        printf("Generated seed '%s' from mnemonic '%s'.\n\n", seed_str, valid_mnemonics[i]);
        char mnemonic[MONERO_MNEMONIC_MAXIMUM_LENGTH] = { '\0' };
        if (!test_seed(seed_str, mnemonic)) {
            printf("Failed to generate mnemonic from seed '%s'.\n", valid_mnemonics[i]);
            return 1;
        }
        printf("Generated mnemonic '%s' from seed '%s'.\n\n", mnemonic, seed_str);
        if (i == 2) *strrchr(mnemonic, ' ') = '\0';
        char* cpy = malloc(strlen(valid_mnemonics[i])+1);
        strcpy(cpy, valid_mnemonics[i]);
        if (strcmp(uppercase(cpy), uppercase(mnemonic)) != 0) {
            free(cpy);
            printf("Mnemonic mismatch between %s and %s.\n", valid_mnemonics[i], mnemonic);
            return 1;
        }
        free(cpy);
        printf("Original mnemonic '%s' and regenerated mnemonic '%s' match.\n\n", valid_mnemonics[i], mnemonic);
    }
    printf("Checking invalid mnemonics.\n");
    char* invalid_mnemonics[] = {
        //'invalid' not a word in the word list
        "invalid lexicon payment input paddles tequila oxygen tutor cuffs affair vials ongoing pelican badge logic lilac kitchens lexicon portents cuisine jolted moment vegan yellow cuisine",
        //less than 24 words
        "abbey abducts ability ablaze abnormal abort abrasive absorb abyss academy aces aching acidic acoustic acquire across actress acumen adapt addicted adept adhesive adjust"
        //more than 25 words
        "abbey abducts ability ablaze abnormal abort abrasive absorb abyss academy aces aching acidic acoustic acquire across actress acumen adapt addicted adept adhesive adjust across actress aces"
        };
    for (int i = 0; i < sizeof(invalid_mnemonics)/sizeof(char*); i++) {
        char seed_str[65] = { '\0' };
        if (test_mnemonic(invalid_mnemonics[i], seed_str)) {
            printf("Generated seed from invalid mnemonic '%s'.\n", invalid_mnemonics[i]);
            return 1;
        }
    }

    return 0;
}
