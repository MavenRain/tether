module S = Tether_store.Store
let ( let* ) = Result.bind
let checked = ref 0
let require condition label = incr checked; if condition then Ok () else (prerr_endline ("FAIL ABSOLUTE-UNIT " ^ label); Error S.Not_integer)
let expect expected result label = require (result = Ok expected) label
let deadline = S.expire ~absolute:true ~seconds:false
let timestamp = S.ttl ~absolute:true ~seconds:false
let all test xs = List.fold_left (fun acc x -> let* () = acc in test x) (Ok ()) xs
let run () =
  let* clock = S.advance "1000" S.empty in
  let data = [S.Str "7"; S.Str "\000\255"; S.Hash ["f", "7"]; S.List ["a"; "b"];
    S.Set ["a"; "b"]; S.ZSet ["a", "1"]; S.Stream ["id", "v"]] in
  let* () = all (fun value ->
    let base = S.put "key" value (S.put "other" (S.Str "kept") clock) in
    let* () = expect "-1" (timestamp "key" base) "persistent sentinel" in
    let* () = expect "-2" (timestamp "absent" base) "missing sentinel" in
    let* changed, timed = deadline "key" "1500" base in
    let* () = require (changed = "1" && timed.now = 1000L && S.bindings timed = S.bindings base) "preserve values and clock" in
    let* () = expect "1500" (timestamp "key" timed) "absolute milliseconds" in
    let* () = expect "500" (S.ttl ~seconds:false "key" timed) "relative interoperability" in
    let* () = expect "2" (S.ttl ~absolute:true ~seconds:true "key" timed) "round half up" in
    let* later = S.advance "300" timed in
    let* () = expect "1500" (timestamp "key" later) "deadline survives clock advance" in
    let* () = expect "200" (S.ttl ~seconds:false "key" later) "elapsed relative lifetime" in
    let* boundary = S.advance "500" timed in
    let* () = expect "1500" (timestamp "key" boundary) "alive at deadline" in
    let* expired = S.advance "1" boundary in
    let* () = require (S.bindings expired = ["other", S.Str "kept"] && S.Keys.is_empty expired.deadlines) "expired metadata removed" in
    let* () = all (fun amount -> let* count, after = deadline "key" amount timed in
      require (count = "1" && S.bindings after = S.bindings expired && S.Keys.is_empty after.deadlines) "past or current timestamp deletes")
      ["1000"; "999"; "0"; "-1"; "-9223372036854775808"] in
    let _, persisted = S.persist "key" timed in
    let* () = expect "-1" (timestamp "key" persisted) "persist clears absolute expiry" in
    let _, replaced = S.set "key" "fresh" timed in
    let* () = expect "-1" (timestamp "key" replaced) "set clears absolute expiry" in
    let* () = expect "-1" (timestamp "key" base) "old snapshot unchanged" in
    let* _, seconds = S.expire ~absolute:true ~seconds:true "key" "2" base in
    expect "2000" (timestamp "key" seconds) "absolute seconds scale") data in
  let base = S.put "key" (S.Str "v") clock in
  let* () = expect ("0", clock) (deadline "absent" "9223372036854775807" clock) "missing maximum timestamp" in
  let* _, maximum = deadline "key" "9223372036854775807" base in
  let* () = require (S.Keys.find_opt "key" maximum.deadlines = Some Int64.max_int) "absolute has no clock addition" in
  let* () = require (timestamp "key" maximum = Error S.Expire_reply) "maximum reply refused" in
  let* () = all (fun initial ->
    let* () = all (fun amount -> require (S.expire ~absolute:true ~seconds:true "key" amount initial = Error (S.Expire_range "expireat")) "seconds overflow before key lookup")
      ["9223372036854776"; "-9223372036854776"] in
    all (fun amount -> require (deadline "key" amount initial = Error S.Not_integer) "invalid timestamp")
      ["01"; "+1"; "-0"; "1.5"; "9223372036854775808"]) [clock; base] in
  let* () = require (S.message (S.Expire_range "expireat") = "ERR invalid expire time in 'expireat' command") "absolute error names command" in
  let* () = all (fun (ms, seconds) -> let* _, timed = deadline "key" ms (S.put "key" (S.Str "v") S.empty) in
    expect seconds (S.ttl ~absolute:true ~seconds:true "key" timed) "second rounding")
    ["1", "0"; "499", "0"; "500", "1"; "999", "1"; "1000", "1"; "1499", "1"; "1500", "2"] in
  let* _, exact = deadline "key" "9007199254740991" base in
  let* () = expect "9007199254740991" (timestamp "key" exact) "largest exact timestamp" in
  let* () = all (fun amount -> let* _, timed = deadline "key" amount base in
    require (timestamp "key" timed = Error S.Expire_reply) "inexact timestamp refused") ["9007199254740992"; "9007199254740993"] in
  let* _, relative = S.expire ~seconds:false "key" "1500" base in
  let* () = expect "2500" (timestamp "key" relative) "relative deadline lookup" in
  print_endline ("PASS ABSOLUTE-UNIT cases=" ^ string_of_int !checked); Ok ()
let () = run () |> Result.fold ~ok:Fun.id ~error:(fun error -> prerr_endline (S.message error); exit 1)
