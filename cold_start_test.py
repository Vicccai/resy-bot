#!/usr/bin/env python3
"""
Cold start vs Pre-warmed connection test
Measures the true first request performance difference
"""

import time
import requests
import socket
from requests.adapters import HTTPAdapter

def test_true_cold_start():
    """Test completely cold start - DNS + TCP + SSL + request"""
    print("🧊 Testing TRUE COLD START (DNS + TCP + SSL + Request):")
    
    # Flush DNS cache by using IP directly for comparison
    test_url = "https://httpbin.org/delay/0.05"  # 50ms server delay
    
    results = []
    for i in range(3):
        # Create completely fresh session
        session = requests.Session()
        
        start_time = time.time()
        try:
            response = session.get(test_url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"  Cold start {i+1} failed: {e}")
            session.close()
            continue
        end_time = time.time()
        
        duration = end_time - start_time
        results.append(duration)
        session.close()
        
        print(f"  Cold start {i+1}: {duration:.3f}s")
        time.sleep(1)  # Wait between tests to ensure fresh connections
    
    avg = sum(results) / len(results) if results else 0
    print(f"  Cold start average: {avg:.3f}s")
    return avg

def test_pre_warmed_connection():
    """Test pre-warmed connection approach"""
    print("\n🔥 Testing PRE-WARMED CONNECTION:")
    
    test_url = "https://httpbin.org/delay/0.05"  # 50ms server delay
    
    # Set up optimized session
    session = requests.Session()
    adapter = HTTPAdapter(
        pool_connections=20,
        pool_maxsize=50,
        max_retries=0,
        pool_block=False
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.timeout = (1.0, 3.0)
    
    # Pre-warm the connection
    print("  Pre-warming connection...")
    try:
        warmup_start = time.time()
        warmup_resp = session.get("https://httpbin.org/status/200", timeout=5)
        warmup_time = time.time() - warmup_start
        print(f"  Pre-warm took: {warmup_time:.3f}s")
    except Exception as e:
        print(f"  Pre-warming failed: {e}")
        return 0
    
    # Now test the actual request using the warmed connection
    results = []
    for i in range(3):
        start_time = time.time()
        try:
            response = session.get(test_url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"  Warmed request {i+1} failed: {e}")
            continue
        end_time = time.time()
        
        duration = end_time - start_time
        results.append(duration)
        
        print(f"  Warmed request {i+1}: {duration:.3f}s")
        time.sleep(0.1)  # Small delay
    
    session.close()
    
    avg = sum(results) / len(results) if results else 0
    print(f"  Pre-warmed average: {avg:.3f}s")
    return avg

def test_connection_components():
    """Break down the connection overhead components"""
    print("\n🔬 MEASURING CONNECTION COMPONENTS:")
    
    # DNS resolution time
    print("  Measuring DNS resolution...")
    dns_times = []
    for i in range(3):
        start = time.time()
        ip = socket.gethostbyname("httpbin.org")
        dns_time = (time.time() - start) * 1000
        dns_times.append(dns_time)
        print(f"    DNS lookup {i+1}: {dns_time:.2f}ms")
    
    avg_dns = sum(dns_times) / len(dns_times)
    print(f"  Average DNS time: {avg_dns:.2f}ms")
    
    # TCP + SSL handshake time
    print("\n  Measuring TCP + SSL handshake...")
    handshake_times = []
    for i in range(3):
        session = requests.Session()
        start = time.time()
        try:
            # First request establishes connection
            resp = session.get("https://httpbin.org/status/200", timeout=5)
            handshake_time = (time.time() - start) * 1000
            handshake_times.append(handshake_time)
            print(f"    Handshake {i+1}: {handshake_time:.2f}ms")
        except Exception as e:
            print(f"    Handshake {i+1} failed: {e}")
        session.close()
        time.sleep(0.5)  # Brief pause
    
    avg_handshake = sum(handshake_times) / len(handshake_times) if handshake_times else 0
    print(f"  Average handshake time: {avg_handshake:.2f}ms")
    
    return avg_dns, avg_handshake

def main():
    print("Cold Start vs Pre-Warmed Connection Analysis")
    print("=" * 60)
    print("This measures the TRUE first request performance difference")
    print("=" * 60)
    
    # Measure individual components
    dns_time, handshake_time = test_connection_components()
    
    # Test cold start performance
    cold_start_time = test_true_cold_start()
    
    # Test pre-warmed performance
    pre_warmed_time = test_pre_warmed_connection()
    
    # Analysis
    print("\n" + "=" * 60)
    print("PERFORMANCE ANALYSIS")
    print("=" * 60)
    
    print(f"DNS resolution overhead: {dns_time:.1f}ms")
    print(f"TCP + SSL handshake overhead: {handshake_time:.1f}ms")
    print(f"Total connection overhead: {dns_time + handshake_time:.1f}ms")
    
    print(f"\nCold start time: {cold_start_time:.3f}s")
    print(f"Pre-warmed time: {pre_warmed_time:.3f}s")
    
    if cold_start_time > 0 and pre_warmed_time > 0:
        speedup = cold_start_time / pre_warmed_time
        time_saved = (cold_start_time - pre_warmed_time) * 1000
        print(f"\n🚀 Pre-warming speedup: {speedup:.2f}x")
        print(f"⚡ Time saved by pre-warming: {time_saved:.1f}ms")
        
        # Calculate the overhead eliminated
        connection_overhead = dns_time + handshake_time
        actual_savings = time_saved
        efficiency = (actual_savings / connection_overhead) * 100 if connection_overhead > 0 else 0
        print(f"📊 Overhead elimination efficiency: {efficiency:.1f}%")
    
    print("\n" + "=" * 60)
    print("RESY BOT FIRST REQUEST IMPLICATIONS:")
    print("=" * 60)
    print("• Cold start includes full DNS + TCP + SSL overhead")
    print("• Pre-warming eliminates connection setup time")
    print("• Critical for resy: first request must be fastest")
    print("• Every millisecond of overhead eliminated = competitive advantage")
    print(f"• Estimated resy API savings: {time_saved:.0f}ms per booking attempt")
    print("=" * 60)

if __name__ == "__main__":
    main() 