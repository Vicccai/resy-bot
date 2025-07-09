#!/usr/bin/env python3
"""
Performance testing script for ResyBot
Tests both sync and async modes to help optimize performance
"""

import asyncio
import time
import json
import argparse
from typing import Dict, List
from resy_bot.logging import logging
from resy_bot.models import ResyConfig, ReservationRequest, TimedReservationRequest
from resy_bot.manager import ResyManager
from resy_bot.model_builders import build_find_request_body

logger = logging.getLogger(__name__)
logger.setLevel("INFO")


def test_sync_request_speed(manager: ResyManager, reservation_request: ReservationRequest) -> Dict:
    """Test sync request speed"""
    try:
        body = build_find_request_body(reservation_request)
        
        start_time = time.time()
        slots = manager.api_access.find_booking_slots(body)
        end_time = time.time()
        
        return {
            "success": True,
            "duration": end_time - start_time,
            "slots_found": len(slots),
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "duration": None,
            "slots_found": 0,
            "error": str(e)
        }


async def test_async_request_speed(manager: ResyManager, reservation_request: ReservationRequest) -> Dict:
    """Test async request speed"""
    try:
        import aiohttp
        
        body = build_find_request_body(reservation_request)
        find_url = "https://api.resy.com/4/find"
        
        headers = {
            "Authorization": manager.config.get_authorization(),
            "X-Resy-Auth-Token": manager.config.token,
            "X-Resy-Universal-Auth": manager.config.token,
            "Origin": "https://resy.com",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0",
            "Cache-Control": "no-cache",
        }
        
        timeout = aiohttp.ClientTimeout(total=10, connect=2)
        connector = aiohttp.TCPConnector(
            limit=10,
            limit_per_host=10,
            enable_cleanup_closed=True,
            use_dns_cache=True,
            ttl_dns_cache=300
        )
        
        start_time = time.time()
        async with aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers=headers
        ) as session:
            async with session.get(find_url, params=body.dict()) as resp:
                resp_json = await resp.json()
                slots = resp_json.get("results", {}).get("venues", [{}])[0].get("slots", [])
                
        end_time = time.time()
        
        return {
            "success": True,
            "duration": end_time - start_time,
            "slots_found": len(slots),
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "duration": None,
            "slots_found": 0,
            "error": str(e)
        }


def run_performance_tests(config_path: str, reservation_path: str, num_tests: int = 10):
    """Run performance tests comparing sync vs async"""
    
    with open(config_path, "r") as f:
        config_data = json.load(f)
    
    with open(reservation_path, "r") as f:
        reservation_data = json.load(f)
    
    config = ResyConfig(**config_data)
    manager = ResyManager.build(config)
    
    timed_request = TimedReservationRequest(**reservation_data)
    reservation_request = timed_request.reservation_request
    
    print(f"Running {num_tests} performance tests...")
    print(f"Venue ID: {reservation_request.venue_id}")
    print(f"Target date: {reservation_request.target_date}")
    print(f"Party size: {reservation_request.party_size}")
    print("=" * 60)
    
    # Test sync performance
    sync_results = []
    print("Testing sync mode...")
    for i in range(num_tests):
        result = test_sync_request_speed(manager, reservation_request)
        sync_results.append(result)
        if result["success"]:
            print(f"  Test {i+1}: {result['duration']:.3f}s ({result['slots_found']} slots)")
        else:
            print(f"  Test {i+1}: FAILED - {result['error']}")
    
    # Test async performance
    async_results = []
    print("\nTesting async mode...")
    for i in range(num_tests):
        result = asyncio.run(test_async_request_speed(manager, reservation_request))
        async_results.append(result)
        if result["success"]:
            print(f"  Test {i+1}: {result['duration']:.3f}s ({result['slots_found']} slots)")
        else:
            print(f"  Test {i+1}: FAILED - {result['error']}")
    
    # Calculate statistics
    sync_durations = [r["duration"] for r in sync_results if r["success"]]
    async_durations = [r["duration"] for r in async_results if r["success"]]
    
    print("\n" + "=" * 60)
    print("PERFORMANCE RESULTS")
    print("=" * 60)
    
    if sync_durations:
        sync_avg = sum(sync_durations) / len(sync_durations)
        sync_min = min(sync_durations)
        sync_max = max(sync_durations)
        print(f"Sync mode  - Avg: {sync_avg:.3f}s, Min: {sync_min:.3f}s, Max: {sync_max:.3f}s")
    else:
        print("Sync mode  - All tests failed")
    
    if async_durations:
        async_avg = sum(async_durations) / len(async_durations)
        async_min = min(async_durations)
        async_max = max(async_durations)
        print(f"Async mode - Avg: {async_avg:.3f}s, Min: {async_min:.3f}s, Max: {async_max:.3f}s")
    else:
        print("Async mode - All tests failed")
    
    if sync_durations and async_durations:
        speedup = sync_avg / async_avg
        print(f"\nAsync speedup: {speedup:.2f}x")
        
        if speedup > 1.1:
            print("✅ Recommendation: Use --async-mode for better performance")
        elif speedup < 0.9:
            print("✅ Recommendation: Use sync mode (default) for better performance")
        else:
            print("ℹ️  Recommendation: Both modes perform similarly")
    
    print("\n" + "=" * 60)
    print("OPTIMIZATION TIPS:")
    print("• Run the bot from a server with low latency to Resy's servers")
    print("• Use a fast internet connection")
    print("• Test both modes to see which works better for your setup")
    print("• Consider running multiple instances with different configurations")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="ResyBot Performance Tester",
        description="Test performance of sync vs async modes",
    )
    
    parser.add_argument("resy_config_path", help="Path to resy configuration file")
    parser.add_argument("reservation_config_path", help="Path to reservation configuration file")
    parser.add_argument("--num-tests", type=int, default=10, help="Number of tests to run (default: 10)")
    
    args = parser.parse_args()
    
    run_performance_tests(args.resy_config_path, args.reservation_config_path, args.num_tests) 