# B4 OPEN items

## Token TTL

The architecture documents describe workspace tokens as short-lived and renewable, but do not define a definitive business TTL constant. The frequently mentioned 15-minute ceiling is a deployment parameter, not an architectural requirement in this slice. No default TTL is embedded in code.

## Token signing and key management

The token signature/encryption algorithm, key rotation, key storage, and gateway trust-bootstrap scheme are not defined by the architecture documents. This slice only defines the API and verification contract shape and stores/accepts a token hash in the fake adapter.

## Persistent issuance and idempotency facts

The MySQL models and migrations for workspace sessions, idempotency records, token hashes, snapshots, and revoke audit facts remain for a later slice. The current fake adapter is process-local and is not a persistence contract.
