/* sort.c
 * trice twin corpus, program 2 of 4: the sort.
 * Five sort routines over one deterministic array, cross-checked.
 * The program reads no input, prints a fixed report and exits 0.
 * The twin of this file in trice is written at Stage C.
 */

#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef uint32_t u32;
typedef uint64_t u64;

#define DATA_N 4096
#define RADIX_BITS 8
#define RADIX_BUCKETS 256

/* ---- deterministic data ---- */

static u32 lcg_next(u32 state)
{
    return (u32)(state * 1664525u + 1013904223u);
}

static void fill_data(u32 *out, u32 n, u32 seed)
{
    u32 state = seed;
    u32 i = 0;
    while (i < n) {
        state = lcg_next(state);
        out[i] = state >> 3;
        i = i + 1u;
    }
}

static void copy_data(u32 *dst, const u32 *src, u32 n)
{
    memcpy(dst, src, (size_t)n * sizeof(u32));
}

static u64 checksum_of(const u32 *a, u32 n)
{
    u64 h = 0xcbf29ce484222325ULL;
    u32 i = 0;
    while (i < n) {
        h = (h ^ (u64)a[i]) * 0x100000001b3ULL;
        i = i + 1u;
    }
    return h;
}

static int is_sorted(const u32 *a, u32 n)
{
    u32 i = 1;
    while (i < n) {
        if (a[i - 1u] > a[i]) {
            return 0;
        }
        i = i + 1u;
    }
    return 1;
}

static int same_array(const u32 *a, const u32 *b, u32 n)
{
    return memcmp(a, b, (size_t)n * sizeof(u32)) == 0;
}

static void swap_at(u32 *a, u32 i, u32 j)
{
    u32 t = a[i];
    a[i] = a[j];
    a[j] = t;
}

/* ---- insertion sort ---- */

static void insertion_sort(u32 *a, u32 n)
{
    u32 i = 1;
    while (i < n) {
        u32 key = a[i];
        u32 j = i;
        while (j > 0u && a[j - 1u] > key) {
            a[j] = a[j - 1u];
            j = j - 1u;
        }
        a[j] = key;
        i = i + 1u;
    }
}

/* ---- binary insertion sort ---- */

static u32 upper_bound(const u32 *a, u32 lo, u32 hi, u32 key)
{
    u32 l = lo;
    u32 h = hi;
    while (l < h) {
        u32 mid = l + ((h - l) >> 1);
        if (a[mid] <= key) {
            l = mid + 1u;
        } else {
            h = mid;
        }
    }
    return l;
}

static void binary_insertion_sort(u32 *a, u32 n)
{
    u32 i = 1;
    while (i < n) {
        u32 key = a[i];
        u32 pos = upper_bound(a, 0u, i, key);
        u32 j = i;
        while (j > pos) {
            a[j] = a[j - 1u];
            j = j - 1u;
        }
        a[pos] = key;
        i = i + 1u;
    }
}

/* ---- merge sort ---- */

static void merge_run(const u32 *src, u32 *dst, u32 lo, u32 mid, u32 hi)
{
    u32 i = lo;
    u32 j = mid;
    u32 k = lo;
    while (k < hi) {
        int take_left = (i < mid) && ((j >= hi) || (src[i] <= src[j]));
        if (take_left != 0) {
            dst[k] = src[i];
            i = i + 1u;
        } else {
            dst[k] = src[j];
            j = j + 1u;
        }
        k = k + 1u;
    }
}

static void merge_sort(u32 *a, u32 *scratch, u32 n)
{
    u32 width = 1;
    u32 *src = a;
    u32 *dst = scratch;
    while (width < n) {
        u32 lo = 0;
        while (lo < n) {
            u32 mid = lo + width;
            u32 hi = lo + 2u * width;
            u32 m = (mid < n) ? mid : n;
            u32 h = (hi < n) ? hi : n;
            merge_run(src, dst, lo, m, h);
            lo = lo + 2u * width;
        }
        u32 *tmp = src;
        src = dst;
        dst = tmp;
        width = width * 2u;
    }
    if (src != a) {
        copy_data(a, src, n);
    }
}

/* ---- quicksort with a median of three and an explicit stack ---- */

#define QUICK_STACK 64

static u32 median_of_three(const u32 *a, u32 lo, u32 hi)
{
    u32 mid = lo + ((hi - lo) >> 1);
    u32 x = a[lo];
    u32 y = a[mid];
    u32 z = a[hi];
    u32 pick = mid;
    if ((x <= y && y <= z) || (z <= y && y <= x)) {
        pick = mid;
    } else if ((y <= x && x <= z) || (z <= x && x <= y)) {
        pick = lo;
    } else {
        pick = hi;
    }
    return pick;
}

static u32 partition_at(u32 *a, u32 lo, u32 hi)
{
    u32 pick = median_of_three(a, lo, hi);
    u32 pivot;
    u32 i = lo;
    u32 j = lo;
    swap_at(a, pick, hi);
    pivot = a[hi];
    while (j < hi) {
        if (a[j] <= pivot) {
            swap_at(a, i, j);
            i = i + 1u;
        }
        j = j + 1u;
    }
    swap_at(a, i, hi);
    return i;
}

static void quick_sort(u32 *a, u32 n)
{
    u32 stack_lo[QUICK_STACK];
    u32 stack_hi[QUICK_STACK];
    u32 top = 0;
    if (n < 2u) {
        return;
    }
    stack_lo[top] = 0u;
    stack_hi[top] = n - 1u;
    top = top + 1u;
    while (top > 0u) {
        u32 lo;
        u32 hi;
        top = top - 1u;
        lo = stack_lo[top];
        hi = stack_hi[top];
        while (lo < hi) {
            u32 p = partition_at(a, lo, hi);
            int left_small = (p - lo) < (hi - p);
            if (left_small != 0) {
                if (p > lo && top < (u32)QUICK_STACK) {
                    stack_lo[top] = lo;
                    stack_hi[top] = p - 1u;
                    top = top + 1u;
                }
                lo = p + 1u;
            } else {
                if (p + 1u < hi && top < (u32)QUICK_STACK) {
                    stack_lo[top] = p + 1u;
                    stack_hi[top] = hi;
                    top = top + 1u;
                }
                hi = (p > lo) ? (p - 1u) : lo;
            }
        }
    }
}

/* ---- heap sort ---- */

static void sift_down(u32 *a, u32 root, u32 n)
{
    u32 parent = root;
    while ((2u * parent + 1u) < n) {
        u32 child = 2u * parent + 1u;
        u32 right = child + 1u;
        if (right < n && a[right] > a[child]) {
            child = right;
        }
        if (a[parent] >= a[child]) {
            return;
        }
        swap_at(a, parent, child);
        parent = child;
    }
}

static void heap_sort(u32 *a, u32 n)
{
    u32 i = n / 2u;
    while (i > 0u) {
        i = i - 1u;
        sift_down(a, i, n);
    }
    i = n;
    while (i > 1u) {
        i = i - 1u;
        swap_at(a, 0u, i);
        sift_down(a, 0u, i);
    }
}

/* ---- radix sort, four passes of eight bits ---- */

static void radix_pass(const u32 *src, u32 *dst, u32 n, unsigned shift)
{
    u32 count[RADIX_BUCKETS];
    u32 prefix[RADIX_BUCKETS];
    u32 i = 0;
    u32 running = 0;
    while (i < (u32)RADIX_BUCKETS) {
        count[i] = 0u;
        i = i + 1u;
    }
    i = 0;
    while (i < n) {
        u32 key = (src[i] >> shift) & (u32)(RADIX_BUCKETS - 1);
        count[key] = count[key] + 1u;
        i = i + 1u;
    }
    i = 0;
    while (i < (u32)RADIX_BUCKETS) {
        prefix[i] = running;
        running = running + count[i];
        i = i + 1u;
    }
    i = 0;
    while (i < n) {
        u32 key = (src[i] >> shift) & (u32)(RADIX_BUCKETS - 1);
        dst[prefix[key]] = src[i];
        prefix[key] = prefix[key] + 1u;
        i = i + 1u;
    }
}

static void radix_sort(u32 *a, u32 *scratch, u32 n)
{
    radix_pass(a, scratch, n, 0u);
    radix_pass(scratch, a, n, RADIX_BITS);
    radix_pass(a, scratch, n, 2u * RADIX_BITS);
    radix_pass(scratch, a, n, 3u * RADIX_BITS);
}

/* ---- the report ---- */

static u32 data[DATA_N];
static u32 work[DATA_N];
static u32 scratch[DATA_N];
static u32 reference[DATA_N];

static void report_one(const char *name, u32 n, u64 sum, int sorted, int agrees)
{
    printf("SORT name=%s n=%lu checksum=%016llx sorted=%d agrees=%d\n",
           name, (unsigned long)n, (unsigned long long)sum, sorted, agrees);
}

static int run_case(const char *name, u32 n, void (*sorter)(u32 *, u32), u64 *out_sum)
{
    int sorted;
    int agrees;
    copy_data(work, data, n);
    sorter(work, n);
    sorted = is_sorted(work, n);
    agrees = same_array(work, reference, n);
    *out_sum = checksum_of(work, n);
    report_one(name, n, *out_sum, sorted, agrees);
    return (sorted != 0 && agrees != 0) ? 1 : 0;
}

static void merge_entry(u32 *a, u32 n)
{
    merge_sort(a, scratch, n);
}

static void radix_entry(u32 *a, u32 n)
{
    radix_sort(a, scratch, n);
}

int main(void)
{
    u32 n = (u32)DATA_N;
    u64 sums[6];
    int ok = 1;
    u32 i = 0;

    fill_data(data, n, 0x2545f491u);
    copy_data(reference, data, n);
    insertion_sort(reference, n);
    sums[0] = checksum_of(reference, n);
    report_one("reference", n, sums[0], is_sorted(reference, n), 1);

    ok = ok & run_case("insertion", n, insertion_sort, &sums[1]);
    ok = ok & run_case("binary_insertion", n, binary_insertion_sort, &sums[2]);
    ok = ok & run_case("merge", n, merge_entry, &sums[3]);
    ok = ok & run_case("quick", n, quick_sort, &sums[4]);
    ok = ok & run_case("heap", n, heap_sort, &sums[5]);

    copy_data(work, data, n);
    radix_entry(work, n);
    printf("SORT name=radix n=%lu checksum=%016llx sorted=%d agrees=%d\n",
           (unsigned long)n, (unsigned long long)checksum_of(work, n),
           is_sorted(work, n), same_array(work, reference, n));
    ok = ok & ((is_sorted(work, n) != 0 && same_array(work, reference, n) != 0) ? 1 : 0);

    while (i < 6u) {
        ok = ok & ((sums[i] == sums[0]) ? 1 : 0);
        i = i + 1u;
    }

    printf("SORT first=%lu last=%lu\n",
           (unsigned long)reference[0], (unsigned long)reference[n - 1u]);
    printf("SORT agreement=%d\n", ok);
    printf("SORT ok\n");
    return 0;
}
