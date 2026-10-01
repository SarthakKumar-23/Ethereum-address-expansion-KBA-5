# Ethereum Address Expansion

This project investigates scalable ways to expand an existing Ethereum address identity dataset without processing the entire Ethereum blockchain/node data.

## Seed Dataset

The initial dataset contains known Ethereum addresses with associated identities.

## Approaches
1. Nansen
2. Bitquery
3. Dune
4. Alchemy

## Current Approach

Nansen is being evaluated first.

### Nansen Experiment

known addresses -> Nansen indexed data -> Related addresses -> Deduplication -> New candidate addresses -> Identity validation

## Goal

Measure:

- number of seed addresses queried
- related addresses discovered
- unique addresses discovered
- addresses already known
- genuinely new candidates
- relationship types
- API errors
- API usage/cost