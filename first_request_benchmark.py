#!/usr/bin/env python3
"""
Benchmark to measure first request time improvements
Tests the actual first request performance before/after optimizations
"""

import time
import requests
import aiohttp
import asyncio
import socket
from requests.adapters import HTTPAdapter
from typing import Dict, List

def test_original_first_request_time(num_tests: int = 10) -> Dict:
    """Test original approach - new session every time, no optimizations"""
    results = []
    test_url = "https://httpbin.org/delay/0.1"  # Simulates resy API with 100ms server delay
    
    print("Testing ORIGINAL first request approach:")
    for i in range(num_tests):
        # Create fresh session every time (no connection reuse)
        session = requests.Session()
        
        start_time = time.time()
        try:
            # This simulates the original first request behavior
            response = session.get(test_url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"  Request {i+1} failed: {e}")
            session.close()
            continue
        end_time = time.time()
        
        duration = end_time - start_time
        results.append(duration)
        session.close()  # Close connection (no reuse)
        
        print(f"  Request {i+1}: {duration:.3f}s")
        time.sleep(0.1)  # Small delay between tests
    
    return {
        'avg': sum(results) / len(results) if results else 0,
        'min': min(results) if results else 0,
        'max': max(results) if results else 0,
        'results': results
    }

def test_optimized_first_request_time(num_tests: int = 10) -> Dict:
    """Test optimized approach - pre-warmed connection, DNS pre-resolved"""
    results = []
    test_url = "https://httpbin.org/delay/0.1"
    
    print("\nTesting OPTIMIZED first request approach:")
    
    # Pre-resolve DNS (simulate our DNS pre-resolution)
    try:
        hostname = "httpbin.org"
        ip = socket.gethostbyname(hostname)
        print(f"  Pre-resolved {hostname} to {ip}")
    except Exception as e:
        print(f"  DNS pre-resolution failed: {e}")
    
    # Create optimized session (simulate our FastHTTPAdapter)
    session = requests.Session()
    adapter = HTTPAdapter(
        pool_connections=20,
        pool_maxsize=50,
        max_retries=0,
        pool_block=False
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.timeout = (1.0, 3.0)  # Our optimized timeouts
    
    # Pre-warm connection
    try:
        print("  Pre-warming connection...")
        warmup_start = time.time()
        warmup_resp = session.get("https://httpbin.org/status/200", timeout=5)
        warmup_end = time.time()
        print(f"  Connection pre-warmed in {(warmup_end - warmup_start):.3f}s")
    except Exception as e:
        print(f"  Connection pre-warming failed: {e}")
    
    for i in range(num_tests):
        start_time = time.time()
        try:
            # This simulates our optimized first request
            response = session.get(test_url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"  Request {i+1} failed: {e}")
            continue
        end_time = time.time()
        
        duration = end_time - start_time
        results.append(duration)
        
        print(f"  Request {i+1}: {duration:.3f}s")
        time.sleep(0.1)  # Small delay between tests
    
    session.close()
    
    return {
        'avg': sum(results) / len(results) if results else 0,
        'min': min(results) if results else 0,
        'max': max(results) if results else 0,
        'results': results
    }

async def test_async_first_request_time(num_tests: int = 10) -> Dict:
    """Test async optimized approach"""
    results = []
    test_url = "https://httpbin.org/delay/0.1"
    
    print("\nTesting ASYNC OPTIMIZED first request approach:")
    
    # Configure optimized async connector
    timeout = aiohttp.ClientTimeout(total=10, connect=2)
    connector = aiohttp.TCPConnector(
        limit=10,
        limit_per_host=10,
        enable_cleanup_closed=True,
        use_dns_cache=True,
        ttl_dns_cache=300
    )
    
    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector
    ) as session:
        
        # Pre-warm async connection
        try:
            print("  Pre-warming async connection...")
            warmup_start = time.time()
            async with session.get("https://httpbin.org/status/200") as resp:
                await resp.read()
            warmup_end = time.time()
            print(f"  Async connection pre-warmed in {(warmup_end - warmup_start):.3f}s")
        except Exception as e:
            print(f"  Async connection pre-warming failed: {e}")
        
        for i in range(num_tests):
            start_time = time.time()
            try:
                async with session.get(test_url) as response:
                    response.raise_for_status()
                    await response.read()
            except Exception as e:
                print(f"  Request {i+1} failed: {e}")
                continue
            end_time = time.time()
            
            duration = end_time - start_time
            results.append(duration)
            
            print(f"  Request {i+1}: {duration:.3f}s")
            await asyncio.sleep(0.1)  # Small delay between tests
    
    return {
        'avg': sum(results) / len(results) if results else 0,
        'min': min(results) if results else 0,
        'max': max(results) if results else 0,
        'results': results
    }

def measure_connection_overhead():
    """Measure the specific overhead components"""
    print("\nMeasuring connection overhead components:")
    
    # DNS resolution time
    start = time.time()
    ip = socket.gethostbyname("httpbin.org")
    dns_time = (time.time() - start) * 1000
    print(f"  DNS resolution: {dns_time:.2f}ms")
    
    # TCP + SSL handshake time (first request to HTTPS)
    session = requests.Session()
    start = time.time()
    try:
        resp = session.get("https://httpbin.org/status/200", timeout=5)
        handshake_time = (time.time() - start) * 1000
        print(f"  First HTTPS request (TCP+SSL): {handshake_time:.2f}ms")
    except Exception as e:
        print(f"  Handshake measurement failed: {e}")
    
    # Subsequent request time (connection reuse)
    start = time.time()
    try:
        resp = session.get("https://httpbin.org/status/200", timeout=5)
        reuse_time = (time.time() - start) * 1000
        print(f"  Subsequent request (reused): {reuse_time:.2f}ms")
    except Exception as e:
        print(f"  Reuse measurement failed: {e}")
    
    session.close()

def main():
    print("First Request Performance Benchmark")
    print("=" * 60)
    print("Testing with httpbin.org (100ms artificial server delay)")
    print("This simulates the resy API first request scenario")
    print("=" * 60)
    
    # Measure connection overhead components
    measure_connection_overhead()
    
    # Test original approach
    original_results = test_original_first_request_time(5)
    
    # Test optimized approach
    optimized_results = test_optimized_first_request_time(5)
    
    # Test async optimized approach
    async_results = asyncio.run(test_async_first_request_time(5))
    
    # Compare results
    print("\n" + "=" * 60)
    print("FIRST REQUEST PERFORMANCE COMPARISON")
    print("=" * 60)
    
    print(f"Original approach    - Avg: {original_results['avg']:.3f}s, Min: {original_results['min']:.3f}s, Max: {original_results['max']:.3f}s")
    print(f"Optimized approach   - Avg: {optimized_results['avg']:.3f}s, Min: {optimized_results['min']:.3f}s, Max: {optimized_results['max']:.3f}s")
    print(f"Async optimized      - Avg: {async_results['avg']:.3f}s, Min: {async_results['min']:.3f}s, Max: {async_results['max']:.3f}s")
    
    if original_results['avg'] > 0 and optimized_results['avg'] > 0:
        speedup = original_results['avg'] / optimized_results['avg']
        time_saved = (original_results['avg'] - optimized_results['avg']) * 1000
        print(f"\n🚀 First request speedup: {speedup:.2f}x")
        print(f"⚡ Time saved on first request: {time_saved:.1f}ms")
        
        if async_results['avg'] > 0:
            async_speedup = original_results['avg'] / async_results['avg']
            async_time_saved = (original_results['avg'] - async_results['avg']) * 1000
            print(f"🔄 Async first request speedup: {async_speedup:.2f}x")
            print(f"⚡ Async time saved: {async_time_saved:.1f}ms")
    
    print("\n" + "=" * 60)
    print("RESY BOT IMPLICATIONS:")
    print("• Every millisecond counts when slots drop")
    print("• Connection pre-warming eliminates handshake overhead")
    print("• DNS pre-resolution saves lookup time")
    print("• Optimized timeouts prevent slow failures")
    print("• Async may provide additional edge depending on system")
    print("=" * 60)

if __name__ == "__main__":
    main() 