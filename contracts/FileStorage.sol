// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * @title FileStorage
 * @notice Stores SHA-256 hashes of encrypted files on-chain.
 *         Each Ethereum address can store multiple file records.
 *         Records are immutable once written — providing tamper evidence.
 */
contract FileStorage {

    struct File {
        string hash;        // SHA-256 hex string of the encrypted file
        uint256 timestamp;  // Block timestamp at upload
    }

    // owner address => list of file records
    mapping(address => File[]) private files;

    event FileStored(address indexed owner, string hash, uint256 timestamp);

    /**
     * @notice Store a new file hash for the calling address.
     * @param _hash  SHA-256 hex string of the encrypted file.
     */
    function storeFile(string memory _hash) public {
        files[msg.sender].push(File(_hash, block.timestamp));
        emit FileStored(msg.sender, _hash, block.timestamp);
    }

    /**
     * @notice Retrieve a stored file record by index.
     * @param user   The address that uploaded the file.
     * @param index  Zero-based index into that user's file list.
     */
    function getFile(address user, uint256 index)
        public view
        returns (string memory, uint256)
    {
        require(index < files[user].length, "Index out of bounds");
        File memory f = files[user][index];
        return (f.hash, f.timestamp);
    }

    /**
     * @notice How many files has an address stored?
     */
    function getFileCount(address user) public view returns (uint256) {
        return files[user].length;
    }
}
