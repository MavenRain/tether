/* spine.c
 * trice twin corpus, program 1 of 4: the spine.
 * A long straight-line arithmetic spine over 64-bit words.
 * The program reads no input, prints a fixed report and exits 0.
 * The twin of this file in trice is written at Stage C.
 */

#include <stdint.h>
#include <stdio.h>

typedef uint32_t u32;
typedef uint64_t u64;

#define SPINE_STAGES 16
#define SPINE_ROUNDS 4096
#define SPINE_SEED 0x9e3779b97f4a7c15ULL

/* ---- primitive mixers ---- */

static u64 rotl64(u64 x, unsigned r)
{
    unsigned s = r & 63u;
    return (s == 0u) ? x : ((x << s) | (x >> (64u - s)));
}

static u64 rotr64(u64 x, unsigned r)
{
    unsigned s = r & 63u;
    return (s == 0u) ? x : ((x >> s) | (x << (64u - s)));
}

static u64 mix_split(u64 x)
{
    u64 z = x + 0x9e3779b97f4a7c15ULL;
    z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
    z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL;
    return z ^ (z >> 31);
}

static u64 mix_xorshift(u64 x)
{
    u64 z = x;
    z ^= z << 13;
    z ^= z >> 7;
    z ^= z << 17;
    return z;
}

static u64 mix_murmur(u64 x)
{
    u64 z = x;
    z ^= z >> 33;
    z *= 0xff51afd7ed558ccdULL;
    z ^= z >> 33;
    z *= 0xc4ceb9fe1a85ec53ULL;
    z ^= z >> 33;
    return z;
}

static u64 mix_fnv(u64 x)
{
    u64 h = 0xcbf29ce484222325ULL;
    unsigned i = 0;
    while (i < 8u) {
        h ^= (x >> (i * 8u)) & 0xffULL;
        h *= 0x100000001b3ULL;
        i = i + 1u;
    }
    return h;
}

/* ---- the sixteen spine stages ---- */

static u64 stage_00(u64 x) { return x + 0x0123456789abcdefULL; }
static u64 stage_01(u64 x) { return rotl64(x, 7) ^ 0x5555555555555555ULL; }
static u64 stage_02(u64 x) { return mix_split(x); }
static u64 stage_03(u64 x) { return x * 0x2545f4914f6cdd1dULL; }
static u64 stage_04(u64 x) { return rotr64(x, 13) + 0x3333333333333333ULL; }
static u64 stage_05(u64 x) { return mix_xorshift(x | 1ULL); }
static u64 stage_06(u64 x) { return x ^ rotl64(x, 29); }
static u64 stage_07(u64 x) { return mix_murmur(x); }
static u64 stage_08(u64 x) { return (x >> 11) | (x << 53); }
static u64 stage_09(u64 x) { return x + rotl64(x, 17) + rotr64(x, 5); }
static u64 stage_10(u64 x) { return mix_fnv(x); }
static u64 stage_11(u64 x) { return x ^ 0xdeadbeefcafebabeULL; }
static u64 stage_12(u64 x) { return rotl64(x * 3ULL, 23); }
static u64 stage_13(u64 x) { return mix_split(x ^ rotr64(x, 41)); }
static u64 stage_14(u64 x) { return (x & 0xffffffffULL) * 0x9e3779b1ULL + (x >> 32); }
static u64 stage_15(u64 x) { return mix_murmur(rotl64(x, 3) + 1ULL); }

typedef u64 (*stage_fn)(u64);

static stage_fn stage_of(unsigned i)
{
    static const stage_fn table[SPINE_STAGES] = {
        stage_00, stage_01, stage_02, stage_03,
        stage_04, stage_05, stage_06, stage_07,
        stage_08, stage_09, stage_10, stage_11,
        stage_12, stage_13, stage_14, stage_15
    };
    return table[i % (unsigned)SPINE_STAGES];
}

/* ---- iteration combinators ---- */

static u64 apply_n(stage_fn f, u64 x, unsigned n)
{
    u64 acc = x;
    unsigned i = 0;
    while (i < n) {
        acc = f(acc);
        i = i + 1u;
    }
    return acc;
}

static u64 spine_pass(u64 x)
{
    u64 acc = x;
    unsigned i = 0;
    while (i < (unsigned)SPINE_STAGES) {
        acc = stage_of(i)(acc);
        i = i + 1u;
    }
    return acc;
}

static u64 spine_fold(u64 seed, unsigned rounds)
{
    u64 acc = seed;
    u64 sum = 0;
    unsigned i = 0;
    while (i < rounds) {
        acc = spine_pass(acc);
        sum = sum + rotl64(acc, i & 63u);
        i = i + 1u;
    }
    return sum ^ acc;
}

/* ---- a small fixed-point ladder ---- */

static u64 collatz_len(u64 n)
{
    u64 x = n;
    u64 steps = 0;
    while (x > 1ULL && steps < 1000ULL) {
        x = ((x & 1ULL) == 0ULL) ? (x >> 1) : (3ULL * x + 1ULL);
        steps = steps + 1ULL;
    }
    return steps;
}

static u64 collatz_band(u64 lo, u64 hi)
{
    u64 total = 0;
    u64 n = lo;
    while (n < hi) {
        total = total + collatz_len(n);
        n = n + 1ULL;
    }
    return total;
}

static u64 fib_mod(unsigned n, u64 m)
{
    u64 a = 0;
    u64 b = 1;
    unsigned i = 0;
    while (i < n) {
        u64 t = (a + b) % m;
        a = b;
        b = t;
        i = i + 1u;
    }
    return a;
}

static u64 pow_mod(u64 base, u64 exp, u64 m)
{
    u64 result = 1;
    u64 b = base % m;
    u64 e = exp;
    while (e > 0ULL) {
        result = ((e & 1ULL) == 1ULL) ? ((result * b) % m) : result;
        b = (b * b) % m;
        e = e >> 1;
    }
    return result;
}

static u64 gcd64(u64 a, u64 b)
{
    u64 x = a;
    u64 y = b;
    while (y != 0ULL) {
        u64 t = x % y;
        x = y;
        y = t;
    }
    return x;
}

/* ---- sieve over a fixed window ---- */

#define SIEVE_N 20000

static u32 prime_count(void)
{
    static unsigned char flag[SIEVE_N];
    u32 count = 0;
    u32 i = 0;
    while (i < (u32)SIEVE_N) {
        flag[i] = 1u;
        i = i + 1u;
    }
    flag[0] = 0u;
    flag[1] = 0u;
    i = 2;
    while (i * i < (u32)SIEVE_N) {
        if (flag[i] != 0u) {
            u32 j = i * i;
            while (j < (u32)SIEVE_N) {
                flag[j] = 0u;
                j = j + i;
            }
        }
        i = i + 1u;
    }
    i = 0;
    while (i < (u32)SIEVE_N) {
        count = count + (u32)flag[i];
        i = i + 1u;
    }
    return count;
}

/* ---- the report ---- */

static void report_stage(unsigned i, u64 value)
{
    printf("SPINE stage=%02u value=%016llx\n", i, (unsigned long long)value);
}

static u64 stage_probe(unsigned i)
{
    return apply_n(stage_of(i), SPINE_SEED + (u64)i, 64u);
}

int main(void)
{
    u64 checksum = 0;
    unsigned i = 0;

    while (i < (unsigned)SPINE_STAGES) {
        u64 v = stage_probe(i);
        report_stage(i, v);
        checksum = checksum ^ rotl64(v, i & 63u);
        i = i + 1u;
    }

    u64 folded = spine_fold(SPINE_SEED, SPINE_ROUNDS);
    u64 band = collatz_band(1000ULL, 4000ULL);
    u64 fib = fib_mod(90u, 1000000007ULL);
    u64 powm = pow_mod(7ULL, 1000003ULL, 1000000007ULL);
    u64 g = gcd64(1071ULL * 100003ULL, 462ULL * 100003ULL);
    u32 primes = prime_count();

    printf("SPINE folded=%016llx\n", (unsigned long long)folded);
    printf("SPINE collatz_band=%llu\n", (unsigned long long)band);
    printf("SPINE fib90_mod=%llu\n", (unsigned long long)fib);
    printf("SPINE pow_mod=%llu\n", (unsigned long long)powm);
    printf("SPINE gcd=%llu\n", (unsigned long long)g);
    printf("SPINE primes_below_20000=%lu\n", (unsigned long)primes);

    checksum = checksum ^ folded ^ band ^ fib ^ powm ^ g ^ (u64)primes;
    printf("SPINE checksum=%016llx\n", (unsigned long long)checksum);
    printf("SPINE ok\n");
    return 0;
}
