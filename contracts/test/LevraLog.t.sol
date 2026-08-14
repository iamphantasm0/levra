// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Test} from "forge-std/Test.sol";
import {LevraLog} from "../LevraLog.sol";

contract LevraLogTest is Test {
    // NOTE: do not name this `log` — forge-std's Test inherits
    // `event log(string)` from StdAssertions and the identifiers collide.
    LevraLog public levraLog;

    function setUp() public {
        levraLog = new LevraLog();
    }

    function test_LogStoresEntry() public {
        bytes32 specHash = keccak256("test spec");
        levraLog.log(specHash);

        assertEq(levraLog.count(), 1);

        (bytes32 storedHash, uint256 storedTs) = levraLog.getEntry(0);
        assertEq(storedHash, specHash);
        assertGt(storedTs, 0);
    }

    function test_LogEmitsEvent() public {
        bytes32 specHash = keccak256("test spec");
        // specHash is the only indexed arg; checkTopic2/3 must be false.
        vm.expectEmit(true, false, false, true);
        emit LevraLog.SpecLogged(specHash, block.timestamp);
        levraLog.log(specHash);
    }

    function test_MultipleEntriesAreOrdered() public {
        bytes32 h1 = keccak256("first");
        bytes32 h2 = keccak256("second");

        levraLog.log(h1);
        levraLog.log(h2);

        assertEq(levraLog.count(), 2);

        (bytes32 stored1,) = levraLog.getEntry(0);
        (bytes32 stored2,) = levraLog.getEntry(1);
        assertEq(stored1, h1);
        assertEq(stored2, h2);
    }

    function test_DuplicateHashesAreAccepted() public {
        bytes32 specHash = keccak256("same");
        levraLog.log(specHash);
        levraLog.log(specHash);

        assertEq(levraLog.count(), 2);
    }

    function test_CountStartsAtZero() public view {
        assertEq(levraLog.count(), 0);
    }

    function test_TimestampMatchesBlock() public {
        vm.warp(1_777_000_000);
        levraLog.log(keccak256("warped"));

        (, uint256 storedTs) = levraLog.getEntry(0);
        assertEq(storedTs, 1_777_000_000);
    }

    function test_GetEntryRevertsOnOutOfBounds() public {
        vm.expectRevert();
        levraLog.getEntry(0);
    }

    /// @dev Any 32-byte value must round-trip unchanged — the contract must not
    ///      interpret or normalise the hash it is handed.
    function testFuzz_AnyHashRoundTrips(bytes32 specHash) public {
        levraLog.log(specHash);
        (bytes32 storedHash,) = levraLog.getEntry(0);
        assertEq(storedHash, specHash);
    }
}
