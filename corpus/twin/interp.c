/* interp.c
 * trice twin corpus, program 4 of 4: the small calculus interpreter.
 * An untyped lambda calculus with de Bruijn indices, closures, integer
 * primitives and a normaliser, over a fixed table of terms.
 * The program reads no input, prints a fixed report and exits 0.
 * The twin of this file in trice is written at Stage C.
 */

#include <stdint.h>
#include <stdio.h>

typedef int64_t i64;
typedef uint64_t u64;

#define TERM_MAX 8192
#define VALUE_MAX 8192
#define ENV_MAX 8192
#define FUEL 200000

/* ---- terms ---- */

typedef enum {
    TERM_VAR,
    TERM_LAM,
    TERM_APP,
    TERM_LIT,
    TERM_ADD,
    TERM_MUL,
    TERM_SUB,
    TERM_IFZ
} term_kind;

typedef struct {
    term_kind kind;
    int index;
    i64 literal;
    int a;
    int b;
    int c;
} term;

typedef struct {
    term items[TERM_MAX];
    int count;
} term_arena;

static term_arena terms;

static int make_term(term t)
{
    if (terms.count >= TERM_MAX) {
        return 0;
    }
    terms.items[terms.count] = t;
    terms.count = terms.count + 1;
    return terms.count - 1;
}

static term blank_term(term_kind k)
{
    term t;
    t.kind = k;
    t.index = 0;
    t.literal = 0;
    t.a = 0;
    t.b = 0;
    t.c = 0;
    return t;
}

static int term_var(int index)
{
    term t = blank_term(TERM_VAR);
    t.index = index;
    return make_term(t);
}

static int term_lam(int body)
{
    term t = blank_term(TERM_LAM);
    t.a = body;
    return make_term(t);
}

static int term_app(int f, int x)
{
    term t = blank_term(TERM_APP);
    t.a = f;
    t.b = x;
    return make_term(t);
}

static int term_lit(i64 v)
{
    term t = blank_term(TERM_LIT);
    t.literal = v;
    return make_term(t);
}

static int term_bin(term_kind k, int x, int y)
{
    term t = blank_term(k);
    t.a = x;
    t.b = y;
    return make_term(t);
}

static int term_ifz(int scrutinee, int zero_case, int else_case)
{
    term t = blank_term(TERM_IFZ);
    t.a = scrutinee;
    t.b = zero_case;
    t.c = else_case;
    return make_term(t);
}

/* ---- values and environments ---- */

typedef enum {
    VALUE_INT,
    VALUE_CLOSURE,
    VALUE_STUCK
} value_kind;

typedef struct {
    value_kind kind;
    i64 number;
    int body;
    int env;
} value;

typedef struct {
    value items[VALUE_MAX];
    int count;
} value_arena;

typedef struct {
    int head;
    int tail;
} env_cell;

typedef struct {
    env_cell items[ENV_MAX];
    int count;
} env_arena;

static value_arena values;
static env_arena envs;

#define ENV_NIL (-1)

static int make_value(value v)
{
    if (values.count >= VALUE_MAX) {
        return 0;
    }
    values.items[values.count] = v;
    values.count = values.count + 1;
    return values.count - 1;
}

static int value_int(i64 n)
{
    value v;
    v.kind = VALUE_INT;
    v.number = n;
    v.body = 0;
    v.env = ENV_NIL;
    return make_value(v);
}

static int value_closure(int body, int env)
{
    value v;
    v.kind = VALUE_CLOSURE;
    v.number = 0;
    v.body = body;
    v.env = env;
    return make_value(v);
}

static int value_stuck(void)
{
    value v;
    v.kind = VALUE_STUCK;
    v.number = 0;
    v.body = 0;
    v.env = ENV_NIL;
    return make_value(v);
}

static int env_cons(int head, int tail)
{
    if (envs.count >= ENV_MAX) {
        return tail;
    }
    envs.items[envs.count].head = head;
    envs.items[envs.count].tail = tail;
    envs.count = envs.count + 1;
    return envs.count - 1;
}

static int env_nth(int env, int index)
{
    int cur = env;
    int i = index;
    while (cur != ENV_NIL && i > 0) {
        cur = envs.items[cur].tail;
        i = i - 1;
    }
    return (cur == ENV_NIL) ? (-1) : envs.items[cur].head;
}

/* ---- the machine ---- */

static long fuel_used;

static int eval_term(int index, int env);

static int eval_app(const term *t, int env)
{
    int fv = eval_term(t->a, env);
    int xv = eval_term(t->b, env);
    value f;
    if (fv < 0 || xv < 0) {
        return value_stuck();
    }
    f = values.items[fv];
    switch (f.kind) {
    case VALUE_CLOSURE:
        return eval_term(f.body, env_cons(xv, f.env));
    case VALUE_INT:
    case VALUE_STUCK:
        return value_stuck();
    }
    return value_stuck();
}

static int as_int(int slot, i64 *out)
{
    value v;
    if (slot < 0) {
        return 0;
    }
    v = values.items[slot];
    switch (v.kind) {
    case VALUE_INT:
        *out = v.number;
        return 1;
    case VALUE_CLOSURE:
    case VALUE_STUCK:
        return 0;
    }
    return 0;
}

static int eval_arith(const term *t, int env)
{
    i64 x = 0;
    i64 y = 0;
    int lok = as_int(eval_term(t->a, env), &x);
    int rok = as_int(eval_term(t->b, env), &y);
    if (lok == 0 || rok == 0) {
        return value_stuck();
    }
    switch (t->kind) {
    case TERM_ADD: return value_int(x + y);
    case TERM_SUB: return value_int(x - y);
    case TERM_MUL: return value_int(x * y);
    case TERM_VAR:
    case TERM_LAM:
    case TERM_APP:
    case TERM_LIT:
    case TERM_IFZ:
        return value_stuck();
    }
    return value_stuck();
}

static int eval_ifz(const term *t, int env)
{
    i64 scrutinee = 0;
    int ok = as_int(eval_term(t->a, env), &scrutinee);
    if (ok == 0) {
        return value_stuck();
    }
    return (scrutinee == 0) ? eval_term(t->b, env) : eval_term(t->c, env);
}

static int eval_term(int index, int env)
{
    term t;
    fuel_used = fuel_used + 1;
    if (fuel_used > (long)FUEL) {
        return value_stuck();
    }
    if (index < 0 || index >= terms.count) {
        return value_stuck();
    }
    t = terms.items[index];
    switch (t.kind) {
    case TERM_VAR:
        return env_nth(env, t.index);
    case TERM_LAM:
        return value_closure(t.a, env);
    case TERM_APP:
        return eval_app(&t, env);
    case TERM_LIT:
        return value_int(t.literal);
    case TERM_ADD:
    case TERM_SUB:
    case TERM_MUL:
        return eval_arith(&t, env);
    case TERM_IFZ:
        return eval_ifz(&t, env);
    }
    return value_stuck();
}

/* ---- terms of the fixed table ---- */

static int church_numeral(int n)
{
    int body = term_var(0);
    int i = 0;
    while (i < n) {
        body = term_app(term_var(1), body);
        i = i + 1;
    }
    return term_lam(term_lam(body));
}

static int successor_function(void)
{
    return term_lam(term_bin(TERM_ADD, term_var(0), term_lit(1)));
}

static int church_to_int(int church)
{
    return term_app(term_app(church, successor_function()), term_lit(0));
}

static int church_add(int m, int n)
{
    int inner = term_app(term_app(term_var(2), term_var(1)),
                         term_app(term_app(term_var(3), term_var(1)), term_var(0)));
    int plus = term_lam(term_lam(term_lam(term_lam(inner))));
    return term_app(term_app(plus, m), n);
}

static int church_mul(int m, int n)
{
    int inner = term_app(term_app(term_var(3), term_app(term_var(2), term_var(1))),
                         term_var(0));
    int times = term_lam(term_lam(term_lam(term_lam(inner))));
    return term_app(term_app(times, m), n);
}

static int identity_chain(int depth)
{
    int body = term_var(0);
    int result = term_lit(41);
    int i = 0;
    while (i < depth) {
        result = term_app(term_lam(body), result);
        i = i + 1;
    }
    return term_bin(TERM_ADD, result, term_lit(1));
}

static int fold_sum(int upto)
{
    int acc = term_lit(0);
    int i = 1;
    while (i <= upto) {
        acc = term_bin(TERM_ADD, acc, term_lit((i64)i));
        i = i + 1;
    }
    return acc;
}

static int branch_ladder(int depth)
{
    int result = term_lit(7);
    int i = 0;
    while (i < depth) {
        result = term_ifz(term_bin(TERM_SUB, term_lit((i64)i), term_lit((i64)i)),
                          term_bin(TERM_ADD, result, term_lit(2)),
                          term_bin(TERM_MUL, result, term_lit(3)));
        i = i + 1;
    }
    return result;
}

static int applied_twice(void)
{
    int twice = term_lam(term_lam(term_app(term_var(1), term_app(term_var(1), term_var(0)))));
    int add_five = term_lam(term_bin(TERM_ADD, term_var(0), term_lit(5)));
    return term_app(term_app(twice, add_five), term_lit(100));
}

/* ---- the report ---- */

typedef struct {
    const char *name;
    int root;
} case_row;

static u64 fold_case(u64 acc, const char *name, i64 value, int ok)
{
    u64 h = acc;
    int i = 0;
    while (name[i] != '\0') {
        h = (h ^ (u64)(unsigned char)name[i]) * 0x100000001b3ULL;
        i = i + 1;
    }
    h = (h ^ (u64)value) * 0x100000001b3ULL;
    h = (h ^ (u64)ok) * 0x100000001b3ULL;
    return h;
}

int main(void)
{
    case_row rows[10];
    u64 digest = 0xcbf29ce484222325ULL;
    int stuck = 0;
    int i = 0;

    terms.count = 0;
    values.count = 0;
    envs.count = 0;

    rows[0].name = "church_3_to_int";
    rows[0].root = church_to_int(church_numeral(3));
    rows[1].name = "church_add_4_5";
    rows[1].root = church_to_int(church_add(church_numeral(4), church_numeral(5)));
    rows[2].name = "church_mul_6_7";
    rows[2].root = church_to_int(church_mul(church_numeral(6), church_numeral(7)));
    rows[3].name = "identity_chain_64";
    rows[3].root = identity_chain(64);
    rows[4].name = "fold_sum_100";
    rows[4].root = fold_sum(100);
    rows[5].name = "branch_ladder_16";
    rows[5].root = branch_ladder(16);
    rows[6].name = "applied_twice";
    rows[6].root = applied_twice();
    rows[7].name = "church_add_10_10";
    rows[7].root = church_to_int(church_add(church_numeral(10), church_numeral(10)));
    rows[8].name = "church_mul_12_12";
    rows[8].root = church_to_int(church_mul(church_numeral(12), church_numeral(12)));
    rows[9].name = "nested_lit";
    rows[9].root = term_app(term_lam(term_bin(TERM_MUL, term_var(0), term_var(0))),
                            term_lit(11));

    while (i < 10) {
        i64 result = 0;
        int slot;
        int ok;
        fuel_used = 0;
        slot = eval_term(rows[i].root, ENV_NIL);
        ok = as_int(slot, &result);
        stuck = stuck + ((ok == 0) ? 1 : 0);
        if (ok != 0) {
            printf("INTERP case=%s value=%lld steps=%ld\n",
                   rows[i].name, (long long)result, fuel_used);
        } else {
            printf("INTERP case=%s stuck steps=%ld\n", rows[i].name, fuel_used);
        }
        digest = fold_case(digest, rows[i].name, result, ok);
        i = i + 1;
    }

    printf("INTERP terms=%d values=%d envs=%d\n",
           terms.count, values.count, envs.count);
    printf("INTERP stuck=%d\n", stuck);
    printf("INTERP digest=%016llx\n", (unsigned long long)digest);
    printf("INTERP ok\n");
    return 0;
}
