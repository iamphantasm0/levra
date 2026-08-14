// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Test, console} from "forge-std/Test.sol";
import {LevraLog} from "../LevraLog.sol";

contract LevraLogTest is Test {
    LevraLog public log;

    function setUp() public {
        log = new LevraLog();
    }

    function test_LogStoresEntry() public {
        bytes32 hash = keccak256("test spec");
        log.log(hash);

        assertEq(log.count(), 1);

        (bytes32 storedHash, uint256 storedTs) = log.getEntry(0);
        assertEq(storedHash, hash);
        assertGt(storedTs, 0);
    }

    function test_LogEmitsEvent() public {
        bytes32 hash = keccak256("test spec");
        vm.expectEmit(true, true, false, true);
        emit LevraLog.SpecLogged(hash, block.timestamp);
        log.log(hash);
    }

    function test_MultipleEntriesAreOrdered() public {
        bytes32 h1 = keccak256("first");
        bytes32 h2 = keccak256("second");

        log.log(h1);
        log.log(h2);

        assertEq(log.count(), 2);

        (bytes32 stored1,) = log.getEntry(0);
        (bytes32 stored2,) = log.getEntry(1);
        assertEq(stored1, h1);
        assertEq(stored2, h2);
    }

    function test_DuplicateHashesAreAccepted() public {
        bytes32 hash = keccak256("same");
        log.log(hash);
        log.log(hash);

        assertEq(log.count(), 2);
    }
}