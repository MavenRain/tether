/* parser.c
 * trice twin corpus, program 3 of 4: the parser.
 * A recursive descent parser and evaluator for an integer expression
 * grammar with let bindings, over a fixed table of source strings.
 * The program reads no input, prints a fixed report and exits 0.
 * The twin of this file in trice is written at Stage C.
 */

#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef int64_t i64;
typedef uint64_t u64;

#define TOKEN_MAX 512
#define IDENT_MAX 16
#define ENV_MAX 32
#define NODE_MAX 2048

/* ---- tokens ---- */

typedef enum {
    TOK_END,
    TOK_NUMBER,
    TOK_IDENT,
    TOK_LET,
    TOK_IN,
    TOK_PLUS,
    TOK_MINUS,
    TOK_STAR,
    TOK_SLASH,
    TOK_PERCENT,
    TOK_CARET,
    TOK_LPAREN,
    TOK_RPAREN,
    TOK_EQUAL,
    TOK_BAD
} token_kind;

typedef struct {
    token_kind kind;
    i64 number;
    char text[IDENT_MAX];
} token;

typedef struct {
    token items[TOKEN_MAX];
    int count;
} token_list;

static int is_space_char(char c)
{
    return (c == ' ' || c == '\t' || c == '\n' || c == '\r') ? 1 : 0;
}

static int is_digit_char(char c)
{
    return (c >= '0' && c <= '9') ? 1 : 0;
}

static int is_alpha_char(char c)
{
    int lower = (c >= 'a' && c <= 'z') ? 1 : 0;
    int upper = (c >= 'A' && c <= 'Z') ? 1 : 0;
    int under = (c == '_') ? 1 : 0;
    return (lower + upper + under > 0) ? 1 : 0;
}

static token_kind keyword_of(const char *text)
{
    if (strcmp(text, "let") == 0) {
        return TOK_LET;
    }
    if (strcmp(text, "in") == 0) {
        return TOK_IN;
    }
    return TOK_IDENT;
}

static token_kind punct_of(char c)
{
    switch (c) {
    case '+': return TOK_PLUS;
    case '-': return TOK_MINUS;
    case '*': return TOK_STAR;
    case '/': return TOK_SLASH;
    case '%': return TOK_PERCENT;
    case '^': return TOK_CARET;
    case '(': return TOK_LPAREN;
    case ')': return TOK_RPAREN;
    case '=': return TOK_EQUAL;
    default: return TOK_BAD;
    }
}

static void push_token(token_list *out, token t)
{
    if (out->count < TOKEN_MAX) {
        out->items[out->count] = t;
        out->count = out->count + 1;
    }
}

static int lex_source(const char *src, token_list *out)
{
    int i = 0;
    out->count = 0;
    while (src[i] != '\0') {
        token t;
        memset(&t, 0, sizeof(t));
        if (is_space_char(src[i]) != 0) {
            i = i + 1;
            continue;
        }
        if (is_digit_char(src[i]) != 0) {
            i64 value = 0;
            while (is_digit_char(src[i]) != 0) {
                value = value * 10 + (i64)(src[i] - '0');
                i = i + 1;
            }
            t.kind = TOK_NUMBER;
            t.number = value;
            push_token(out, t);
            continue;
        }
        if (is_alpha_char(src[i]) != 0) {
            int n = 0;
            while ((is_alpha_char(src[i]) != 0 || is_digit_char(src[i]) != 0)
                   && n < IDENT_MAX - 1) {
                t.text[n] = src[i];
                n = n + 1;
                i = i + 1;
            }
            t.text[n] = '\0';
            t.kind = keyword_of(t.text);
            push_token(out, t);
            continue;
        }
        t.kind = punct_of(src[i]);
        i = i + 1;
        push_token(out, t);
        if (t.kind == TOK_BAD) {
            return 0;
        }
    }
    {
        token end;
        memset(&end, 0, sizeof(end));
        end.kind = TOK_END;
        push_token(out, end);
    }
    return 1;
}

/* ---- the tree ---- */

typedef enum {
    NODE_NUMBER,
    NODE_VAR,
    NODE_ADD,
    NODE_SUB,
    NODE_MUL,
    NODE_DIV,
    NODE_MOD,
    NODE_POW,
    NODE_NEG,
    NODE_LET,
    NODE_ERROR
} node_kind;

typedef struct {
    node_kind kind;
    i64 number;
    char name[IDENT_MAX];
    int left;
    int right;
    int body;
} node;

typedef struct {
    node items[NODE_MAX];
    int count;
} node_arena;

typedef struct {
    const token_list *tokens;
    int pos;
    node_arena *arena;
    int failed;
} parser_state;

static int alloc_node(parser_state *p, node n)
{
    if (p->arena->count >= NODE_MAX) {
        p->failed = 1;
        return 0;
    }
    p->arena->items[p->arena->count] = n;
    p->arena->count = p->arena->count + 1;
    return p->arena->count - 1;
}

static token peek_token(const parser_state *p)
{
    int index = (p->pos < p->tokens->count) ? p->pos : (p->tokens->count - 1);
    return p->tokens->items[index];
}

static void advance_token(parser_state *p)
{
    p->pos = (p->pos + 1 < p->tokens->count) ? (p->pos + 1) : p->pos;
}

static int accept_kind(parser_state *p, token_kind k)
{
    if (peek_token(p).kind == k) {
        advance_token(p);
        return 1;
    }
    return 0;
}

static int parse_expr(parser_state *p);

static int parse_atom(parser_state *p)
{
    token t = peek_token(p);
    node n;
    memset(&n, 0, sizeof(n));
    if (t.kind == TOK_NUMBER) {
        advance_token(p);
        n.kind = NODE_NUMBER;
        n.number = t.number;
        return alloc_node(p, n);
    }
    if (t.kind == TOK_IDENT) {
        advance_token(p);
        n.kind = NODE_VAR;
        memcpy(n.name, t.text, IDENT_MAX);
        return alloc_node(p, n);
    }
    if (t.kind == TOK_LPAREN) {
        int inner;
        advance_token(p);
        inner = parse_expr(p);
        if (accept_kind(p, TOK_RPAREN) == 0) {
            p->failed = 1;
        }
        return inner;
    }
    p->failed = 1;
    n.kind = NODE_ERROR;
    return alloc_node(p, n);
}

static int parse_unary(parser_state *p)
{
    if (accept_kind(p, TOK_MINUS) != 0) {
        node n;
        memset(&n, 0, sizeof(n));
        n.kind = NODE_NEG;
        n.left = parse_unary(p);
        return alloc_node(p, n);
    }
    return parse_atom(p);
}

static int parse_power(parser_state *p)
{
    int base = parse_unary(p);
    if (accept_kind(p, TOK_CARET) != 0) {
        node n;
        memset(&n, 0, sizeof(n));
        n.kind = NODE_POW;
        n.left = base;
        n.right = parse_power(p);
        return alloc_node(p, n);
    }
    return base;
}

static node_kind factor_kind(token_kind k)
{
    switch (k) {
    case TOK_STAR: return NODE_MUL;
    case TOK_SLASH: return NODE_DIV;
    case TOK_PERCENT: return NODE_MOD;
    default: return NODE_ERROR;
    }
}

static int parse_factor(parser_state *p)
{
    int left = parse_power(p);
    while (1) {
        node_kind k = factor_kind(peek_token(p).kind);
        node n;
        if (k == NODE_ERROR) {
            return left;
        }
        advance_token(p);
        memset(&n, 0, sizeof(n));
        n.kind = k;
        n.left = left;
        n.right = parse_power(p);
        left = alloc_node(p, n);
    }
}

static int parse_term(parser_state *p)
{
    int left = parse_factor(p);
    while (1) {
        token_kind k = peek_token(p).kind;
        node n;
        if (k != TOK_PLUS && k != TOK_MINUS) {
            return left;
        }
        advance_token(p);
        memset(&n, 0, sizeof(n));
        n.kind = (k == TOK_PLUS) ? NODE_ADD : NODE_SUB;
        n.left = left;
        n.right = parse_factor(p);
        left = alloc_node(p, n);
    }
}

static int parse_expr(parser_state *p)
{
    if (accept_kind(p, TOK_LET) != 0) {
        token name = peek_token(p);
        node n;
        memset(&n, 0, sizeof(n));
        if (name.kind != TOK_IDENT) {
            p->failed = 1;
            n.kind = NODE_ERROR;
            return alloc_node(p, n);
        }
        advance_token(p);
        if (accept_kind(p, TOK_EQUAL) == 0) {
            p->failed = 1;
        }
        n.kind = NODE_LET;
        memcpy(n.name, name.text, IDENT_MAX);
        n.left = parse_expr(p);
        if (accept_kind(p, TOK_IN) == 0) {
            p->failed = 1;
        }
        n.body = parse_expr(p);
        return alloc_node(p, n);
    }
    return parse_term(p);
}

/* ---- evaluation ---- */

typedef struct {
    char names[ENV_MAX][IDENT_MAX];
    i64 values[ENV_MAX];
    int count;
} env;

typedef struct {
    i64 value;
    int ok;
} outcome;

static outcome ok_value(i64 v)
{
    outcome r;
    r.value = v;
    r.ok = 1;
    return r;
}

static outcome bad_value(void)
{
    outcome r;
    r.value = 0;
    r.ok = 0;
    return r;
}

static outcome lookup_env(const env *e, const char *name)
{
    int i = e->count;
    while (i > 0) {
        i = i - 1;
        if (strcmp(e->names[i], name) == 0) {
            return ok_value(e->values[i]);
        }
    }
    return bad_value();
}

static void bind_env(env *e, const char *name, i64 value)
{
    if (e->count < ENV_MAX) {
        memcpy(e->names[e->count], name, IDENT_MAX);
        e->values[e->count] = value;
        e->count = e->count + 1;
    }
}

static i64 power_int(i64 base, i64 exp)
{
    i64 result = 1;
    i64 b = base;
    i64 e = (exp < 0) ? 0 : exp;
    while (e > 0) {
        result = ((e & 1) == 1) ? (result * b) : result;
        b = b * b;
        e = e >> 1;
    }
    return result;
}

static outcome eval_node(const node_arena *a, int index, env *e);

static outcome eval_binary(const node_arena *a, const node *n, env *e)
{
    outcome l = eval_node(a, n->left, e);
    outcome r = eval_node(a, n->right, e);
    if (l.ok == 0 || r.ok == 0) {
        return bad_value();
    }
    switch (n->kind) {
    case NODE_ADD: return ok_value(l.value + r.value);
    case NODE_SUB: return ok_value(l.value - r.value);
    case NODE_MUL: return ok_value(l.value * r.value);
    case NODE_DIV: return (r.value == 0) ? bad_value() : ok_value(l.value / r.value);
    case NODE_MOD: return (r.value == 0) ? bad_value() : ok_value(l.value % r.value);
    case NODE_POW: return ok_value(power_int(l.value, r.value));
    case NODE_NUMBER:
    case NODE_VAR:
    case NODE_NEG:
    case NODE_LET:
    case NODE_ERROR:
        return bad_value();
    }
    return bad_value();
}

static outcome eval_node(const node_arena *a, int index, env *e)
{
    node n;
    if (index < 0 || index >= a->count) {
        return bad_value();
    }
    n = a->items[index];
    switch (n.kind) {
    case NODE_NUMBER:
        return ok_value(n.number);
    case NODE_VAR:
        return lookup_env(e, n.name);
    case NODE_NEG: {
        outcome inner = eval_node(a, n.left, e);
        return (inner.ok == 0) ? bad_value() : ok_value(-inner.value);
    }
    case NODE_LET: {
        outcome bound = eval_node(a, n.left, e);
        outcome body;
        int saved = e->count;
        if (bound.ok == 0) {
            return bad_value();
        }
        bind_env(e, n.name, bound.value);
        body = eval_node(a, n.body, e);
        e->count = saved;
        return body;
    }
    case NODE_ADD:
    case NODE_SUB:
    case NODE_MUL:
    case NODE_DIV:
    case NODE_MOD:
    case NODE_POW:
        return eval_binary(a, &n, e);
    case NODE_ERROR:
        return bad_value();
    }
    return bad_value();
}

/* ---- the report ---- */

static const char *const sources[] = {
    "1 + 2 * 3",
    "(1 + 2) * 3",
    "2 ^ 3 ^ 2",
    "-4 + 10 % 3",
    "let x = 7 in x * x + 1",
    "let a = 2 in let b = 3 in a ^ b + b ^ a",
    "100 / 7 + 100 % 7",
    "let n = 10 in n * (n + 1) / 2",
    "((((1 + 1))))",
    "3 * -4 - -5",
    "let z = 0 in 5 / z",
    "let k = 4 in k ^ (k - 1) - k * k",
    "9 % 4 * 3 + 2 ^ 5",
    "1 - 2 - 3 - 4",
    "let big = 1000000 in big * big / big",
    "2 + missing"
};

static u64 fold_result(u64 acc, i64 value, int ok)
{
    u64 h = acc;
    h = (h ^ (u64)value) * 0x100000001b3ULL;
    h = (h ^ (u64)ok) * 0x100000001b3ULL;
    return h;
}

int main(void)
{
    int count = (int)(sizeof(sources) / sizeof(sources[0]));
    u64 digest = 0xcbf29ce484222325ULL;
    int accepted = 0;
    int refused = 0;
    int i = 0;

    while (i < count) {
        token_list tokens;
        node_arena arena;
        parser_state state;
        env e;
        int root;
        outcome result;

        arena.count = 0;
        e.count = 0;
        state.tokens = &tokens;
        state.pos = 0;
        state.arena = &arena;
        state.failed = 0;

        if (lex_source(sources[i], &tokens) == 0) {
            state.failed = 1;
        }
        root = parse_expr(&state);
        if (peek_token(&state).kind != TOK_END) {
            state.failed = 1;
        }
        result = (state.failed != 0) ? bad_value() : eval_node(&arena, root, &e);

        if (result.ok != 0) {
            accepted = accepted + 1;
            printf("PARSE ok nodes=%d value=%lld source=%s\n",
                   arena.count, (long long)result.value, sources[i]);
        } else {
            refused = refused + 1;
            printf("PARSE refused nodes=%d source=%s\n", arena.count, sources[i]);
        }
        digest = fold_result(digest, result.value, result.ok);
        i = i + 1;
    }

    printf("PARSE cases=%d accepted=%d refused=%d\n", count, accepted, refused);
    printf("PARSE digest=%016llx\n", (unsigned long long)digest);
    printf("PARSE ok\n");
    return 0;
}
