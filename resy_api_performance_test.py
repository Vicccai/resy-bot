#!/usr/bin/env python3
"""
Real Resy API Performance Test
Tests actual performance against api.resy.com with our optimizations
"""

import time
import requests
import aiohttp
import asyncio
import socket
from requests.adapters import HTTPAdapter
from resy_bot.api_access import FastHTTPAdapter, build_session
from resy_bot.models import ResyConfig
from typing import Dict, List

def test_resy_api_cold_start(num_tests: int = 3) -> Dict:
    """Test cold start performance against actual Resy API"""
    print("🧊 Testing COLD START against actual Resy API:")
    
    # Use a lightweight Resy endpoint that doesn't require auth
    # The /4/find endpoint is what we actually use, but without params it should be fast
    resy_url = "https://api.resy.com/4/find"
    
    results = []
    for i in range(num_tests):
        # Create fresh session every time (cold start)
        session = requests.Session()
        
        start_time = time.time()
        try:
            # Test with minimal params to avoid auth issues
            response = session.get(resy_url, params={'day': '2020-01-01'}, timeout=10)
            # Don't check status - we just want timing, even if it returns error
        except Exception as e:
            print(f"  Cold start {i+1} failed: {e}")
            session.close()
            continue
        end_time = time.time()
        
        duration = end_time - start_time
        results.append(duration)
        session.close()
        
        print(f"  Cold start {i+1}: {duration:.3f}s (status: {response.status_code})")
        time.sleep(2)  # Wait between tests for fresh connections
    
    avg = sum(results) / len(results) if results else 0
    print(f"  Cold start average: {avg:.3f}s")
    return {
        'avg': avg,
        'min': min(results) if results else 0,
        'max': max(results) if results else 0,
        'results': results
    }

def test_resy_api_optimized(num_tests: int = 3) -> Dict:
    """Test optimized performance against actual Resy API"""
    print("\n🔥 Testing OPTIMIZED approach against actual Resy API:")
    
    resy_url = "https://api.resy.com/4/find"
    
    # Create optimized session using our FastHTTPAdapter
    session = requests.Session()
    adapter = FastHTTPAdapter(
        pool_connections=20,
        pool_maxsize=50,
        max_retries=0,
        pool_block=False
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.timeout = (1.0, 3.0)  # Our optimized timeouts
    
    # Pre-warm the connection to Resy API
    print("  Pre-warming connection to api.resy.com...")
    try:
        warmup_start = time.time()
        # Use a lightweight endpoint for warmup
        warmup_resp = session.get("https://api.resy.com/4/find", params={'day': '2020-01-01'}, timeout=5)
        warmup_time = time.time() - warmup_start
        print(f"  Pre-warm took: {warmup_time:.3f}s (status: {warmup_resp.status_code})")
    except Exception as e:
        print(f"  Pre-warming failed: {e}")
        session.close()
        return {'avg': 0, 'min': 0, 'max': 0, 'results': []}
    
    # Now test the actual requests using the warmed connection
    results = []
    for i in range(num_tests):
        start_time = time.time()
        try:
            response = session.get(resy_url, params={'day': '2020-01-01'}, timeout=10)
        except Exception as e:
            print(f"  Optimized request {i+1} failed: {e}")
            continue
        end_time = time.time()
        
        duration = end_time - start_time
        results.append(duration)
        
        print(f"  Optimized request {i+1}: {duration:.3f}s (status: {response.status_code})")
        time.sleep(0.5)  # Small delay
    
    session.close()
    
    avg = sum(results) / len(results) if results else 0
    print(f"  Optimized average: {avg:.3f}s")
    return {
        'avg': avg,
        'min': min(results) if results else 0,
        'max': max(results) if results else 0,
        'results': results
    }

async def test_resy_api_async(num_tests: int = 3) -> Dict:
    """Test async optimized performance against actual Resy API"""
    print("\n🚀 Testing ASYNC OPTIMIZED approach against actual Resy API:")
    
    resy_url = "https://api.resy.com/4/find"
    
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
        
        # Pre-warm async connection to Resy API
        try:
            print("  Pre-warming async connection to api.resy.com...")
            warmup_start = time.time()
            async with session.get(resy_url, params={'day': '2020-01-01'}) as resp:
                await resp.read()
            warmup_time = time.time() - warmup_start
            print(f"  Async pre-warm took: {warmup_time:.3f}s (status: {resp.status})")
        except Exception as e:
            print(f"  Async pre-warming failed: {e}")
            return {'avg': 0, 'min': 0, 'max': 0, 'results': []}
        
        results = []
        for i in range(num_tests):
            start_time = time.time()
            try:
                async with session.get(resy_url, params={'day': '2020-01-01'}) as response:
                    await response.read()
            except Exception as e:
                print(f"  Async request {i+1} failed: {e}")
                continue
            end_time = time.time()
            
            duration = end_time - start_time
            results.append(duration)
            
            print(f"  Async request {i+1}: {duration:.3f}s (status: {response.status})")
            await asyncio.sleep(0.5)  # Small delay
    
    avg = sum(results) / len(results) if results else 0
    print(f"  Async average: {avg:.3f}s")
    return {
        'avg': avg,
        'min': min(results) if results else 0,
        'max': max(results) if results else 0,
        'results': results
    }

def test_resy_network_metrics():
    """Test network metrics to Resy API"""
    print("\n🌐 Testing network metrics to api.resy.com:")
    
    # DNS resolution to Resy
    print("  DNS resolution to api.resy.com...")
    dns_times = []
    for i in range(3):
        start = time.time()
        try:
            ip = socket.gethostbyname("api.resy.com")
            dns_time = (time.time() - start) * 1000
            dns_times.append(dns_time)
            print(f"    DNS lookup {i+1}: {dns_time:.2f}ms → {ip}")
        except Exception as e:
            print(f"    DNS lookup {i+1} failed: {e}")
    
    avg_dns = sum(dns_times) / len(dns_times) if dns_times else 0
    print(f"  Average DNS time to Resy: {avg_dns:.2f}ms")
    
    # TCP + SSL handshake to Resy
    print("\n  TCP + SSL handshake to api.resy.com...")
    handshake_times = []
    for i in range(3):
        session = requests.Session()
        start = time.time()
        try:
            resp = session.get("https://api.resy.com/4/find", params={'day': '2020-01-01'}, timeout=5)
            handshake_time = (time.time() - start) * 1000
            handshake_times.append(handshake_time)
            print(f"    Handshake {i+1}: {handshake_time:.2f}ms (status: {resp.status_code})")
        except Exception as e:
            print(f"    Handshake {i+1} failed: {e}")
        session.close()
        time.sleep(1)
    
    avg_handshake = sum(handshake_times) / len(handshake_times) if handshake_times else 0
    print(f"  Average handshake time to Resy: {avg_handshake:.2f}ms")
    
    return avg_dns, avg_handshake

def competitive_analysis(cold_time, optimized_time, async_time):
    """Analyze competitive advantage"""
    print("\n" + "=" * 60)
    print("COMPETITIVE ANALYSIS")
    print("=" * 60)
    
    if cold_time > 0:
        print(f"Most other bots (cold start): {cold_time:.3f}s")
    if optimized_time > 0:
        print(f"Your optimized bot: {optimized_time:.3f}s")
    if async_time > 0:
        print(f"Your async bot: {async_time:.3f}s")
    
    best_time = min([t for t in [optimized_time, async_time] if t > 0])
    
    if cold_time > 0 and best_time > 0:
        advantage = (cold_time - best_time) * 1000
        speedup = cold_time / best_time
        
        print(f"\n🎯 Your competitive advantage: {advantage:.0f}ms faster")
        print(f"🚀 Your speedup vs competitors: {speedup:.2f}x")
        
        # Estimate booking success probability
        if advantage > 500:
            success_rating = "EXCELLENT"
            emoji = "🏆"
        elif advantage > 300:
            success_rating = "VERY GOOD"
            emoji = "🥇"
        elif advantage > 150:
            success_rating = "GOOD"
            emoji = "🥈"
        elif advantage > 50:
            success_rating = "MODERATE"
            emoji = "🥉"
        else:
            success_rating = "POOR"
            emoji = "⚠️"
        
        print(f"{emoji} Booking competitiveness: {success_rating}")
        
        if advantage > 200:
            print("✅ You should be able to book high-demand reservations!")
        elif advantage > 100:
            print("⚡ You have a good chance at popular reservations")
        else:
            print("⚠️  May need additional optimizations for very popular spots")

def main():
    print("Real Resy API Performance Test")
    print("=" * 60)
    print("Testing against actual api.resy.com endpoints")
    print("This shows real-world competitive performance")
    print("=" * 60)
    
    # Test network metrics first
    dns_time, handshake_time = test_resy_network_metrics()
    
    # Test cold start performance
    cold_results = test_resy_api_cold_start(3)
    
    # Test optimized performance
    optimized_results = test_resy_api_optimized(3)
    
    # Test async performance
    async_results = asyncio.run(test_resy_api_async(3))
    
    # Competitive analysis
    competitive_analysis(
        cold_results['avg'],
        optimized_results['avg'], 
        async_results['avg']
    )
    
    print("\n" + "=" * 60)
    print("REAL RESY API PERFORMANCE SUMMARY")
    print("=" * 60)
    print(f"DNS to api.resy.com: {dns_time:.1f}ms")
    print(f"Connection overhead: {handshake_time:.1f}ms")
    print(f"Cold start time: {cold_results['avg']:.3f}s")
    print(f"Optimized time: {optimized_results['avg']:.3f}s")  
    print(f"Async time: {async_results['avg']:.3f}s")
    
    best_time = min([t for t in [optimized_results['avg'], async_results['avg']] if t > 0])
    if cold_results['avg'] > 0 and best_time > 0:
        total_advantage = (cold_results['avg'] - best_time) * 1000
        print(f"\nTotal advantage: {total_advantage:.0f}ms")
        print("This is your edge over unoptimized bots!")
    
    print("=" * 60)

if __name__ == "__main__":
    main() 