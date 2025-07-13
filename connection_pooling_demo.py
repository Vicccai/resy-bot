#!/usr/bin/env python3
"""
Demonstration of connection pooling performance benefits
Shows the difference between reusing connections vs. creating new ones
"""

import time
import requests
import aiohttp
import asyncio
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Dict

def test_without_pooling(urls: List[str], num_requests: int = 5) -> Dict:
    """Test making requests without connection pooling (new session each time)"""
    results = []
    
    for i in range(num_requests):
        # Create new session for each request (no pooling)
        session = requests.Session()
        
        start_time = time.time()
        try:
            for url in urls:
                response = session.get(url, timeout=10)
                response.raise_for_status()
        except Exception as e:
            print(f"Request {i+1} failed: {e}")
            continue
        end_time = time.time()
        
        duration = end_time - start_time
        results.append(duration)
        session.close()  # Close connection after each test
        
        print(f"  Request {i+1}: {duration:.3f}s")
    
    return {
        'avg': sum(results) / len(results) if results else 0,
        'min': min(results) if results else 0,
        'max': max(results) if results else 0,
        'results': results
    }

def test_with_pooling(urls: List[str], num_requests: int = 5) -> Dict:
    """Test making requests with connection pooling (reuse same session)"""
    results = []
    
    # Create single session with connection pooling
    session = requests.Session()
    
    # Configure connection pooling
    adapter = HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=0,
        pool_block=False
    )
    
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    for i in range(num_requests):
        start_time = time.time()
        try:
            for url in urls:
                response = session.get(url, timeout=10)
                response.raise_for_status()
        except Exception as e:
            print(f"Request {i+1} failed: {e}")
            continue
        end_time = time.time()
        
        duration = end_time - start_time
        results.append(duration)
        
        print(f"  Request {i+1}: {duration:.3f}s")
    
    session.close()
    
    return {
        'avg': sum(results) / len(results) if results else 0,
        'min': min(results) if results else 0,
        'max': max(results) if results else 0,
        'results': results
    }

async def test_async_pooling(urls: List[str], num_requests: int = 5) -> Dict:
    """Test async requests with connection pooling"""
    results = []
    
    # Configure async connection pooling
    timeout = aiohttp.ClientTimeout(total=10, connect=5)
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
        
        for i in range(num_requests):
            start_time = time.time()
            try:
                for url in urls:
                    async with session.get(url) as response:
                        response.raise_for_status()
                        await response.read()
            except Exception as e:
                print(f"Request {i+1} failed: {e}")
                continue
            end_time = time.time()
            
            duration = end_time - start_time
            results.append(duration)
            
            print(f"  Request {i+1}: {duration:.3f}s")
    
    return {
        'avg': sum(results) / len(results) if results else 0,
        'min': min(results) if results else 0,
        'max': max(results) if results else 0,
        'results': results
    }

def main():
    # Test URLs (using public APIs that allow testing)
    test_urls = [
        "https://httpbin.org/delay/0.1",  # Simulates 100ms server delay
        "https://httpbin.org/delay/0.1",  # Simulates multiple requests
        "https://httpbin.org/delay/0.1",  # Like resy bot: find → details → book
    ]
    
    print("Connection Pooling Performance Demonstration")
    print("=" * 60)
    print(f"Testing {len(test_urls)} sequential requests per test")
    print(f"Each request has artificial 100ms server delay")
    print("=" * 60)
    
    # Test without pooling
    print("\n1. WITHOUT Connection Pooling (new session each test):")
    no_pool_results = test_without_pooling(test_urls, num_requests=5)
    
    # Test with pooling
    print("\n2. WITH Connection Pooling (reuse same session):")
    pool_results = test_with_pooling(test_urls, num_requests=5)
    
    # Test async pooling
    print("\n3. ASYNC with Connection Pooling:")
    async_results = asyncio.run(test_async_pooling(test_urls, num_requests=5))
    
    # Compare results
    print("\n" + "=" * 60)
    print("PERFORMANCE COMPARISON")
    print("=" * 60)
    
    print(f"Without pooling - Avg: {no_pool_results['avg']:.3f}s, Min: {no_pool_results['min']:.3f}s, Max: {no_pool_results['max']:.3f}s")
    print(f"With pooling    - Avg: {pool_results['avg']:.3f}s, Min: {pool_results['min']:.3f}s, Max: {pool_results['max']:.3f}s")
    print(f"Async pooling   - Avg: {async_results['avg']:.3f}s, Min: {async_results['min']:.3f}s, Max: {async_results['max']:.3f}s")
    
    if no_pool_results['avg'] > 0 and pool_results['avg'] > 0:
        speedup = no_pool_results['avg'] / pool_results['avg']
        print(f"\nConnection pooling speedup: {speedup:.2f}x")
        
        if async_results['avg'] > 0:
            async_speedup = no_pool_results['avg'] / async_results['avg']
            print(f"Async pooling speedup: {async_speedup:.2f}x")
    
    print("\n" + "=" * 60)
    print("WHY CONNECTION POOLING HELPS:")
    print("• Eliminates TCP handshake overhead (20-100ms)")
    print("• Eliminates SSL/TLS handshake overhead (100-200ms)")
    print("• Reuses existing connections (1-10ms vs 140-350ms)")
    print("• Critical for resy bot: 3 sequential requests per booking")
    print("• Saves ~400ms per booking attempt = competitive advantage!")
    print("=" * 60)

if __name__ == "__main__":
    main() 