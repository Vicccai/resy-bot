#!/usr/bin/env python3
"""
Speed test for resy bot optimizations
Tests the actual performance improvements without needing real credentials
"""

import time
import json
import asyncio
from typing import Dict, List
from unittest.mock import Mock, patch, MagicMock

# Mock the resy bot modules to avoid needing real credentials
def mock_resy_response():
    """Mock response that simulates Resy API response"""
    return {
        "results": {
            "venues": [{
                "slots": [{
                    "config": {
                        "id": "mock-id-123",
                        "type": "Dining Room",
                        "token": "mock-token-123"
                    },
                    "date": {
                        "start": "2024-01-15T19:00:00",
                        "end": "2024-01-15T21:00:00"
                    }
                }]
            }]
        }
    }

def mock_details_response():
    """Mock details response"""
    return {
        "book_token": {
            "value": "mock-book-token-456",
            "date_expires": "2024-01-15T19:30:00"
        }
    }

def mock_book_response():
    """Mock booking response"""
    return {
        "resy_token": "mock-resy-token-789"
    }

def test_original_approach():
    """Test the original approach with Pydantic parsing"""
    from resy_bot.models import (
        FindResponseBody, DetailsResponseBody, BookResponseBody,
        PaymentMethod, ResyConfig, ReservationRequest, TimedReservationRequest
    )
    
    # Mock config
    config = ResyConfig(
        api_key="test-key",
        token="test-token", 
        payment_method_id=123,
        email="test@example.com",
        password="test"
    )
    
    results = []
    
    for i in range(10):
        start_time = time.time()
        
        # Simulate the original approach with full Pydantic parsing
        mock_find_response = mock_resy_response()
        parsed_find = FindResponseBody(**mock_find_response)
        slots = parsed_find.results.venues[0].slots
        
        if slots:
            selected_slot = slots[0]
            config_id = selected_slot.config.token
            
            # Parse details response
            mock_details_resp = mock_details_response()
            parsed_details = DetailsResponseBody(**mock_details_resp)
            book_token = parsed_details.book_token.value
            
            # Parse booking response  
            mock_booking_resp = mock_book_response()
            parsed_booking = BookResponseBody(**mock_booking_resp)
            resy_token = parsed_booking.resy_token
        
        end_time = time.time()
        results.append(end_time - start_time)
        
    return {
        'avg': sum(results) / len(results),
        'min': min(results),
        'max': max(results),
        'results': results
    }

def test_optimized_approach():
    """Test the optimized approach with direct JSON parsing"""
    results = []
    
    for i in range(10):
        start_time = time.time()
        
        # Simulate the optimized approach with direct JSON parsing
        mock_find_response = mock_resy_response()
        slots = mock_find_response.get("results", {}).get("venues", [{}])[0].get("slots", [])
        
        if slots:
            selected_slot = slots[0]
            config_id = selected_slot["config"]["token"]
            
            # Direct JSON parsing
            mock_details_resp = mock_details_response()
            book_token = mock_details_resp["book_token"]["value"]
            
            # Direct JSON parsing
            mock_booking_resp = mock_book_response()
            resy_token = mock_booking_resp.get("resy_token")
        
        end_time = time.time()
        results.append(end_time - start_time)
        
    return {
        'avg': sum(results) / len(results),
        'min': min(results),
        'max': max(results),
        'results': results
    }

def test_request_timing():
    """Test the timing of the full request cycle"""
    import requests
    from requests.adapters import HTTPAdapter
    
    # Test URLs that simulate the 3-step resy process
    test_urls = [
        "https://httpbin.org/delay/0.05",  # Find slots
        "https://httpbin.org/delay/0.05",  # Get details  
        "https://httpbin.org/delay/0.05",  # Book reservation
    ]
    
    # Test without connection pooling
    no_pool_times = []
    for i in range(5):
        start_time = time.time()
        for url in test_urls:
            session = requests.Session()
            try:
                resp = session.get(url, timeout=10)
                resp.raise_for_status()
            except:
                pass
            session.close()
        end_time = time.time()
        no_pool_times.append(end_time - start_time)
    
    # Test with connection pooling
    pool_times = []
    session = requests.Session()
    adapter = HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=0,
        pool_block=False
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    for i in range(5):
        start_time = time.time()
        for url in test_urls:
            try:
                resp = session.get(url, timeout=10)
                resp.raise_for_status()
            except:
                pass
        end_time = time.time()
        pool_times.append(end_time - start_time)
    
    session.close()
    
    return {
        'no_pool': {
            'avg': sum(no_pool_times) / len(no_pool_times),
            'min': min(no_pool_times),
            'max': max(no_pool_times)
        },
        'with_pool': {
            'avg': sum(pool_times) / len(pool_times),
            'min': min(pool_times),
            'max': max(pool_times)
        }
    }

def main():
    print("Resy Bot Performance Optimization Test")
    print("=" * 60)
    
    # Test parsing speed
    print("\n1. RESPONSE PARSING SPEED TEST:")
    print("   Testing Pydantic vs Direct JSON parsing")
    print("-" * 40)
    
    print("Original approach (Pydantic parsing):")
    original_results = test_original_approach()
    print(f"  Avg: {original_results['avg']*1000:.2f}ms, Min: {original_results['min']*1000:.2f}ms, Max: {original_results['max']*1000:.2f}ms")
    
    print("\nOptimized approach (Direct JSON parsing):")
    optimized_results = test_optimized_approach()
    print(f"  Avg: {optimized_results['avg']*1000:.2f}ms, Min: {optimized_results['min']*1000:.2f}ms, Max: {optimized_results['max']*1000:.2f}ms")
    
    if optimized_results['avg'] > 0:
        parsing_speedup = original_results['avg'] / optimized_results['avg']
        print(f"\n  ⚡ Parsing speedup: {parsing_speedup:.2f}x")
    
    # Test request timing
    print("\n2. HTTP REQUEST TIMING TEST:")
    print("   Testing connection pooling benefits")
    print("-" * 40)
    
    request_results = test_request_timing()
    
    no_pool = request_results['no_pool']
    with_pool = request_results['with_pool']
    
    print(f"Without pooling - Avg: {no_pool['avg']:.3f}s, Min: {no_pool['min']:.3f}s, Max: {no_pool['max']:.3f}s")
    print(f"With pooling    - Avg: {with_pool['avg']:.3f}s, Min: {with_pool['min']:.3f}s, Max: {with_pool['max']:.3f}s")
    
    if with_pool['avg'] > 0:
        connection_speedup = no_pool['avg'] / with_pool['avg']
        print(f"\n  ⚡ Connection pooling speedup: {connection_speedup:.2f}x")
    
    # Calculate combined improvement
    print("\n" + "=" * 60)
    print("COMBINED PERFORMANCE IMPROVEMENT")
    print("=" * 60)
    
    if optimized_results['avg'] > 0 and with_pool['avg'] > 0:
        total_speedup = (original_results['avg'] + no_pool['avg']) / (optimized_results['avg'] + with_pool['avg'])
        print(f"Total speedup: {total_speedup:.2f}x")
        
        # Calculate time savings for resy bot
        original_time = original_results['avg'] + no_pool['avg']
        optimized_time = optimized_results['avg'] + with_pool['avg']
        time_saved = (original_time - optimized_time) * 1000
        
        print(f"Time saved per booking attempt: {time_saved:.1f}ms")
        print(f"In resy bot context: {time_saved:.1f}ms advantage over competitors")
    
    print("\n" + "=" * 60)
    print("KEY OPTIMIZATIONS SUMMARY:")
    print("• Direct JSON parsing (no Pydantic validation)")
    print("• HTTP connection pooling and reuse")
    print("• Reduced retry delays (50ms → 10ms)")
    print("• Pre-built request data")
    print("• Async support for even better performance")
    print("• Proper error handling (no more crashes)")
    print("=" * 60)

if __name__ == "__main__":
    main() 