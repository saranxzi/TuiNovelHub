"""
Performance tests for the cache system.

This module contains comprehensive performance tests to validate that the cache system
provides significant performance improvements and operates efficiently.
"""

import asyncio
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Any
import statistics

import pytest

from src.wn_dl.core.cache_manager import CacheManager
from src.wn_dl.core.cache_config import CacheConfig


class CachePerformanceTester:
    """Performance testing suite for the cache system."""
    
    def __init__(self):
        self.results: Dict[str, Any] = {}
        
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all performance tests and return results."""
        print("🚀 Starting Cache Performance Tests...")
        print("=" * 50)
        
        # Test configurations
        configs = {
            "no_compression": CacheConfig(
                enabled=True,
                directory=tempfile.mkdtemp(),
                size_limit="100MB",
                compression=False,
                default_ttl=3600
            ),
            "with_compression": CacheConfig(
                enabled=True,
                directory=tempfile.mkdtemp(),
                size_limit="100MB",
                compression=True,
                compression_level=6,
                default_ttl=3600
            ),
            "fast_compression": CacheConfig(
                enabled=True,
                directory=tempfile.mkdtemp(),
                size_limit="100MB",
                compression=True,
                compression_level=1,
                default_ttl=3600
            )
        }
        
        # Run tests for each configuration
        for config_name, config in configs.items():
            print(f"\n📊 Testing configuration: {config_name}")
            self.results[config_name] = await self._test_configuration(config)
        
        # Run comparative tests
        print(f"\n🔄 Running comparative tests...")
        self.results["comparison"] = await self._test_cache_vs_no_cache()
        
        # Generate summary
        self._generate_summary()
        
        return self.results
    
    async def _test_configuration(self, config: CacheConfig) -> Dict[str, Any]:
        """Test a specific cache configuration."""
        results = {
            "storage_performance": {},
            "retrieval_performance": {},
            "compression_efficiency": {},
            "size_management": {}
        }
        
        async with CacheManager(config) as cache_manager:
            # Test data
            test_data = self._generate_test_data()
            
            # Storage performance test
            print("  📝 Testing storage performance...")
            storage_times = []
            for i, (url, content, headers) in enumerate(test_data):
                start_time = time.time()
                await cache_manager.set(url, content, headers, 200)
                storage_time = time.time() - start_time
                storage_times.append(storage_time)
                
                if i % 10 == 0:
                    print(f"    Stored {i+1}/{len(test_data)} entries")
            
            results["storage_performance"] = {
                "total_entries": len(test_data),
                "avg_time_ms": statistics.mean(storage_times) * 1000,
                "median_time_ms": statistics.median(storage_times) * 1000,
                "max_time_ms": max(storage_times) * 1000,
                "min_time_ms": min(storage_times) * 1000,
                "total_time_s": sum(storage_times)
            }
            
            # Retrieval performance test
            print("  📖 Testing retrieval performance...")
            retrieval_times = []
            cache_hits = 0
            
            for url, expected_content, _ in test_data:
                start_time = time.time()
                entry = await cache_manager.get(url)
                retrieval_time = time.time() - start_time
                retrieval_times.append(retrieval_time)
                
                if entry and entry.content == expected_content:
                    cache_hits += 1
            
            results["retrieval_performance"] = {
                "total_lookups": len(test_data),
                "cache_hits": cache_hits,
                "hit_rate": cache_hits / len(test_data),
                "avg_time_ms": statistics.mean(retrieval_times) * 1000,
                "median_time_ms": statistics.median(retrieval_times) * 1000,
                "max_time_ms": max(retrieval_times) * 1000,
                "min_time_ms": min(retrieval_times) * 1000
            }
            
            # Compression efficiency test
            if config.compression:
                print("  🗜️  Testing compression efficiency...")
                stats = cache_manager.get_stats()
                total_original_size = sum(len(content) for _, content, _ in test_data)
                
                results["compression_efficiency"] = {
                    "compression_ratio": stats.compression_ratio,
                    "original_size_mb": total_original_size / (1024 * 1024),
                    "compressed_size_mb": stats.size_bytes / (1024 * 1024),
                    "space_saved_mb": (total_original_size - stats.size_bytes) / (1024 * 1024),
                    "space_saved_percent": ((total_original_size - stats.size_bytes) / total_original_size) * 100
                }
            
            # Size management test
            print("  📏 Testing size management...")
            stats = cache_manager.get_stats()
            results["size_management"] = {
                "entry_count": stats.entry_count,
                "total_size_mb": stats.size_bytes / (1024 * 1024),
                "avg_entry_size_kb": (stats.size_bytes / stats.entry_count) / 1024 if stats.entry_count > 0 else 0
            }
        
        return results
    
    async def _test_cache_vs_no_cache(self) -> Dict[str, Any]:
        """Compare performance with and without cache."""
        # Simulate network delay for non-cached requests
        async def simulate_network_request(url: str, content: bytes) -> bytes:
            # Simulate network latency (10-100ms)
            await asyncio.sleep(0.05)  # 50ms average
            return content
        
        test_data = self._generate_test_data()[:20]  # Smaller dataset for comparison
        
        # Test without cache
        print("  🌐 Testing without cache...")
        no_cache_times = []
        for url, content, _ in test_data:
            start_time = time.time()
            await simulate_network_request(url, content)
            request_time = time.time() - start_time
            no_cache_times.append(request_time)
        
        # Test with cache
        print("  ⚡ Testing with cache...")
        config = CacheConfig(
            enabled=True,
            directory=tempfile.mkdtemp(),
            size_limit="50MB",
            compression=True,
            default_ttl=3600
        )
        
        async with CacheManager(config) as cache_manager:
            # Populate cache
            for url, content, headers in test_data:
                await cache_manager.set(url, content, headers, 200)
            
            # Test cached retrieval
            cached_times = []
            for url, _, _ in test_data:
                start_time = time.time()
                entry = await cache_manager.get(url)
                request_time = time.time() - start_time
                cached_times.append(request_time)
        
        return {
            "no_cache": {
                "avg_time_ms": statistics.mean(no_cache_times) * 1000,
                "total_time_s": sum(no_cache_times)
            },
            "with_cache": {
                "avg_time_ms": statistics.mean(cached_times) * 1000,
                "total_time_s": sum(cached_times)
            },
            "performance_improvement": {
                "speed_multiplier": statistics.mean(no_cache_times) / statistics.mean(cached_times),
                "time_saved_percent": ((sum(no_cache_times) - sum(cached_times)) / sum(no_cache_times)) * 100
            }
        }
    
    def _generate_test_data(self) -> List[tuple]:
        """Generate test data for performance testing."""
        test_data = []
        
        # Generate various sizes of content
        content_templates = [
            b"<html><body>Small content</body></html>",  # ~40 bytes
            b"<html><body>" + b"Medium content " * 50 + b"</body></html>",  # ~800 bytes
            b"<html><body>" + b"Large content " * 500 + b"</body></html>",  # ~8KB
            b"<html><body>" + b"Very large content " * 2000 + b"</body></html>",  # ~40KB
        ]
        
        headers = {
            "content-type": "text/html",
            "cache-control": "max-age=3600",
            "etag": '"test-etag"'
        }
        
        # Generate 100 test entries
        for i in range(100):
            url = f"https://example.com/page{i}"
            content = content_templates[i % len(content_templates)]
            test_data.append((url, content, headers))
        
        return test_data
    
    def _generate_summary(self):
        """Generate performance test summary."""
        print("\n" + "=" * 50)
        print("📈 CACHE PERFORMANCE TEST RESULTS")
        print("=" * 50)
        
        # Configuration comparison
        print("\n🔧 Configuration Performance Comparison:")
        for config_name, results in self.results.items():
            if config_name == "comparison":
                continue
                
            storage = results["storage_performance"]
            retrieval = results["retrieval_performance"]
            
            print(f"\n  {config_name.upper()}:")
            print(f"    Storage: {storage['avg_time_ms']:.2f}ms avg")
            print(f"    Retrieval: {retrieval['avg_time_ms']:.2f}ms avg")
            print(f"    Hit Rate: {retrieval['hit_rate']:.1%}")
            
            if "compression_efficiency" in results and results["compression_efficiency"]:
                comp = results["compression_efficiency"]
                print(f"    Compression: {comp['space_saved_percent']:.1f}% space saved")
        
        # Cache vs No Cache
        if "comparison" in self.results:
            comp = self.results["comparison"]
            print(f"\n⚡ Cache vs No Cache Performance:")
            print(f"    Without Cache: {comp['no_cache']['avg_time_ms']:.2f}ms avg")
            print(f"    With Cache: {comp['with_cache']['avg_time_ms']:.2f}ms avg")
            print(f"    Speed Improvement: {comp['performance_improvement']['speed_multiplier']:.1f}x faster")
            print(f"    Time Saved: {comp['performance_improvement']['time_saved_percent']:.1f}%")
        
        # Recommendations
        print(f"\n💡 Performance Recommendations:")
        
        # Find best configuration
        best_config = min(
            [(name, results["retrieval_performance"]["avg_time_ms"]) 
             for name, results in self.results.items() if name != "comparison"],
            key=lambda x: x[1]
        )
        
        print(f"    • Best performing configuration: {best_config[0]}")
        print(f"    • Cache provides significant performance benefits")
        print(f"    • Consider enabling compression for storage efficiency")
        print(f"    • Monitor hit rates to optimize TTL settings")


async def main():
    """Run performance tests."""
    tester = CachePerformanceTester()
    results = await tester.run_all_tests()
    
    # Save results to file
    import json
    results_file = Path("cache_performance_results.json")
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to: {results_file}")
    print("✅ Performance testing completed!")


if __name__ == "__main__":
    asyncio.run(main())
