# Monero Airgapped Signing Standard

## Overview
This document formalizes the airgapped signing process used by monero-wallet-cli. The standard defines the communication protocols and data formats between the online and offline components of the wallet.

## Process Flow

1. **Transaction Preparation (Online)**
   - Generate unsigned transaction data
   - Export in standardized format

2. **Signing (Offline)**
   - Import unsigned transaction
   - Sign transaction
   - Export signed transaction

3. **Broadcast (Online)**
   - Import signed transaction
   - Broadcast to network

## Data Formats

### Unsigned Transaction Format