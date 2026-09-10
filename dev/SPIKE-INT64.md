# Spike (g): the 2^53 boundary

Date: 2026-09-09.  kanon pin: 2c2e6e6831a0b2cf3107fa4aad392606109a2bcf.  Brief: /Users/oobi/Documents/tether-m0/stage-0-brief.md section 3.9.  Ruling: R-X2 (RATIFICATIONS.md:26).  Gate: S0-G9.

Tools, read on this machine on 2026-09-09:

```
$ luajit -v
LuaJIT 2.1.1787165859 -- Copyright (C) 2005-2026 Mike Pall. https://luajit.org/
$ jq --version
jq-1.6
```

Every command below ran once through /Users/oobi/Documents/tether-m0/spikes/int64/run.sh, which writes each command, its stdout plus stderr and its exit code to one file each under /Users/oobi/Documents/tether-m0/spikes/int64/.  Every output is verbatim.  Every exit code was 0.  Every output matched the expected line of the brief, so this spike has no finding.

## 1 luajit -joff, number path, rounding at 2^53+1

Expected: 9007199254740992.

```
$ luajit -joff -e "print(string.format('%d', tonumber('9007199254740993')))"
9007199254740992
```

Result: as expected.  The literal 2^53+1 is not representable as a double, so tonumber rounds it to 2^53 with no message.

## 2 luajit -joff, number path, the clamp at 2^63

Expected: 9223372036854775807.

```
$ luajit -joff -e "print(string.format('%d', 2^63))"
9223372036854775807
```

Result: as expected.  The double 2^63 sits one past the Int64 maximum, and `%d` clamps it to 2^63-1 with no message.

## 3 luajit, string path

Expected: 9007199254740993, unchanged.

```
$ luajit -joff -e "print('9007199254740993')"
9007199254740993
```

Result: as expected.  A string crosses luajit unchanged.

## 4 jq 1.6, number path

Expected: 9007199254740992.

```
$ jq -n '9007199254740993'
9007199254740992
```

Result: as expected.  jq 1.6 parses every number as a double, so the literal loses its last bit with no message.

## 5 jq 1.6, string path with --arg

Expected: the digits unchanged.

```
$ jq -n --arg v 9007199254740993 '$v'
"9007199254740993"
```

Result: as expected.  The digits are unchanged inside a JSON string.

## 6 jq 1.6, string path with --args

Expected: the digits unchanged.

```
$ jq -n --args '$ARGS.positional' 9007199254740993
[
  "9007199254740993"
]
```

Result: as expected.  The digits are unchanged inside a JSON string in the positional array.

## 7 What the six lines mean for R-X2

R-X2 rules that every integer that can leave 2^53 crosses both boundaries as a bulk string.  The six lines above show why.  The luajit twin, which runs as `luajit -joff` (R-Q7), holds every number as a double, so a value of 2^53+1 becomes 2^53 in command 1 and a value of 2^63 becomes 2^63-1 in command 2, both without a word.  The REST envelope, which prog.sh builds with `jq -n --args` (R-Q6), meets the same double in jq 1.6, so command 4 destroys the same literal.  On the string path both tools keep every digit: command 3 in luajit, and commands 5 and 6 in jq.  So the only safe carrier across the Lua boundary and across the jq boundary is the string form, which is the Redis bulk string on the wire and a JSON string in the REST body.  Int64 stays a refinement in the types only, and the runtime never converts a value past 2^53 to a number in either tool.  The M0 spine fixture value past 2^53 is 9007199254740993, which is 2^53+1 (S0-D5, R-M0-7).  It is the smallest integer that the number path changes, so a spine that returns 9007199254740993 unchanged proves the bulk-string path and a spine that returns 9007199254740992 proves a number path leaked in.  jq 1.6 is pinned and counted in the trusted base (R-X2), so the version line above is the one every later gate compares against.
