gcc -I ../  -I ../../../ -I ../../trezor-firmware/crypto/ ../../trezor-firmware/crypto/memzero.c ../../uzlib/crc32.c ../legacy_monero_mnemonic.c test.c -o test

#random seed
./test seed a4f9f927ea309d35ecf6a149b3e32cad54d6f769b93eab05311f77472231080f
./test mnemonic stacking lexicon payment input paddles tequila oxygen tutor cuffs affair vials ongoing pelican badge logic lilac kitchens lexicon portents cuisine jolted moment vegan yellow cuisine

#longest possible mnemonic
./test mnemonic verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification verification
./test seed EC050000EC050000EC050000EC050000EC050000EC050000EC050000EC050000

#invalid word 'invalid'
./test mnemonic invalid lexicon payment input paddles tequila oxygen tutor cuffs affair vials ongoing pelican badge logic lilac kitchens lexicon portents cuisine jolted moment vegan yellow cuisine
