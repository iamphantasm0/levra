// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/// @title LevraLog
/// @notice Immutable, append-only log of Levra position spec hashes.
///         One function, one event — small enough to read on a screen.
contract LevraLog {
    /// @dev Each entry stores the keccak256 hash of a generated spec
    ///      plus the block timestamp when it was logged.
    struct Entry {
        bytes32 specHash;
        uint256 timestamp;
    }

    /// @notice All logged entries, in order of insertion.
    Entry[] public entries;

    /// @notice Emitted each time a spec hash is logged.
    event SpecLogged(bytes32 indexed specHash, uint256 timestamp);

    /// @notice Log a position spec hash. Anyone may call — audit trail
    ///         doesn't require permission, it requires openness.
    /// @param specHash The keccak256 hash of the canonical spec bytes.
    function log(bytes32 specHash) external {
        entries.push(Entry({specHash: specHash, timestamp: block.timestamp}));
        emit SpecLogged(specHash, block.timestamp);
    }

    /// @notice Total number of logged entries.
    function count() external view returns (uint256) {
        return entries.length;
    }

    /// @notice Retrieve an entry by index.
    function getEntry(uint256 index) external view returns (bytes32, uint256) {
        Entry memory e = entries[index];
        return (e.specHash, e.timestamp);
    }
}