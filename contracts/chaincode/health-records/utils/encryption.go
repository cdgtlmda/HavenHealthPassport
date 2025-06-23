package utils

import (
    "crypto/aes"
    "crypto/cipher"
    "crypto/rand"
    "crypto/sha256"
    "encoding/base64"
    "encoding/hex"
    "fmt"
    "io"
)

// GenerateDataHash generates a SHA256 hash of the data
func GenerateDataHash(data []byte) string {
    hash := sha256.Sum256(data)
    return hex.EncodeToString(hash[:])
}

// GenerateRecordID generates a unique record ID
func GenerateRecordID() (string, error) {
    b := make([]byte, 16)
    _, err := rand.Read(b)
    if err != nil {
        return "", err
    }
    return hex.EncodeToString(b), nil
}

// EncryptData encrypts data using AES-GCM
func EncryptData(plaintext []byte, key []byte) (string, error) {
    // Create cipher block
    block, err := aes.NewCipher(key)
    if err != nil {
        return "", fmt.Errorf("failed to create cipher: %v", err)
    }

    // Create GCM mode
    aesGCM, err := cipher.NewGCM(block)
    if err != nil {
        return "", fmt.Errorf("failed to create GCM: %v", err)
    }

    // Create nonce
    nonce := make([]byte, aesGCM.NonceSize())
    if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
        return "", fmt.Errorf("failed to create nonce: %v", err)
    }

    // Encrypt data
    ciphertext := aesGCM.Seal(nonce, nonce, plaintext, nil)

    // Encode to base64
    return base64.StdEncoding.EncodeToString(ciphertext), nil
}

// DecryptData decrypts data using AES-GCM
func DecryptData(encryptedData string, key []byte) ([]byte, error) {
    // Decode from base64
    ciphertext, err := base64.StdEncoding.DecodeString(encryptedData)
    if err != nil {
        return nil, fmt.Errorf("failed to decode ciphertext: %v", err)
    }

    // Create cipher block
    block, err := aes.NewCipher(key)
    if err != nil {
        return nil, fmt.Errorf("failed to create cipher: %v", err)
    }

    // Create GCM mode
    aesGCM, err := cipher.NewGCM(block)
    if err != nil {
        return nil, fmt.Errorf("failed to create GCM: %v", err)
    }

    // Extract nonce
    nonceSize := aesGCM.NonceSize()
    if len(ciphertext) < nonceSize {
        return nil, fmt.Errorf("ciphertext too short")
    }

    nonce, ciphertext := ciphertext[:nonceSize], ciphertext[nonceSize:]

    // Decrypt data
    plaintext, err := aesGCM.Open(nil, nonce, ciphertext, nil)
    if err != nil {
        return nil, fmt.Errorf("failed to decrypt: %v", err)
    }

    return plaintext, nil
}

// GenerateEncryptionKey generates a 32-byte encryption key
func GenerateEncryptionKey() ([]byte, error) {
    key := make([]byte, 32)
    if _, err := rand.Read(key); err != nil {
        return nil, err
    }
    return key, nil
}
