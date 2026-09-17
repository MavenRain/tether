module S = Tether_store.Store
let ( let* ) = Result.bind
let checked = ref 0
let check label yes = incr checked; if yes then Ok () else Error label
let ok result = Result.map_error S.message result
let conditions = [S.NX; S.XX; S.GT; S.LT]
let deadline store = S.Keys.find_opt "key" store.S.deadlines
let fixtures = [S.Str "payload"; S.Hash ["f", "v"]; S.List ["a"; "b"];
                S.Set ["m"]; S.ZSet ["m", "1"]; S.Stream ["1-0", "v"]]
let set_at amount store = ok (S.expire ~absolute:true ~seconds:false "key" amount store)

let matrix () =
  let test value =
    let original = S.put "key" value S.empty in
    let* _, volatile = set_at "2000" original in
    let states = [S.empty, None; original, None; volatile, Some 2000L] in
    let test_state (before, old) =
      let test_amount amount =
        let test_condition condition =
          let accepted = S.exists "key" before = "1" && (match condition with
            | S.NX -> Option.is_none old | S.XX -> Option.is_some old
            | S.GT -> old = Some 2000L && amount > 2000L
            | S.LT -> Option.is_none old || amount < 2000L) in
          let* reply, after = ok (S.expire ~condition ~absolute:true ~seconds:false "key" (Int64.to_string amount) before) in
          let* () = check "condition matrix reply" (reply = if accepted then "1" else "0") in
          let* () = check "rejected state unchanged" (accepted || after = before) in
          let* () = check "accepted deadline" (not accepted || deadline after = Some amount) in
          check "payload unchanged" (S.bindings after = S.bindings before) in
        List.fold_left (fun acc condition -> let* () = acc in test_condition condition) (Ok ()) conditions in
      List.fold_left (fun acc amount -> let* () = acc in test_amount amount) (Ok ()) [1000L; 2000L; 3000L] in
    List.fold_left (fun acc state -> let* () = acc in test_state state) (Ok ()) states in
  List.fold_left (fun acc value -> let* () = acc in test value) (Ok ()) fixtures

let boundaries () =
  let original = S.put "key" (S.Str "v") S.empty in
  let* _, volatile = set_at "2000" original in
  let* reply, after = ok (S.expire ~condition:S.GT ~seconds:false "key" "0" volatile) in
  let* () = check "GT rejects deletion" (reply = "0" && after = volatile) in
  let* reply, after = ok (S.expire ~condition:S.LT ~seconds:false "key" "-9223372036854775808" volatile) in
  let* () = check "LT deletes" (reply = "1" && S.bindings after = [] && deadline after = None) in
  let* reply, after = ok (S.expire ~condition:S.NX ~seconds:false "key" "0" original) in
  let* () = check "NX deletes persistent" (reply = "1" && S.bindings after = [] && deadline after = None) in
  let* shifted = ok (S.advance "1000" volatile) in
  let* reply, after = ok (S.expire ~condition:S.GT ~seconds:false "key" "1500" shifted) in
  let* () = check "relative comparison adds clock" (reply = "1" && deadline after = Some 2500L) in
  let* reply, after = ok (S.expire ~condition:S.GT ~absolute:true ~seconds:false "key" "1500" shifted) in
  let* () = check "absolute comparison ignores clock" (reply = "0" && after = shifted) in
  let* _, large = set_at "9007199254740992" original in
  let* reply, after = ok (S.expire ~condition:S.GT ~absolute:true ~seconds:false "key" "9007199254740993" large) in
  let* () = check "exact adjacent deadlines" (reply = "1" && deadline after = Some 9007199254740993L) in
  let* reply, after = ok (S.expire ~condition:S.GT ~absolute:true ~seconds:false "key" "9223372036854775807" original) in
  let* () = check "persistent infinity exceeds int64 max" (reply = "0" && after = original) in
  let* () = check "overflow before condition" (S.expire ~condition:S.GT ~seconds:true "key" "9223372036854776" original = Error (S.Expire_range "expire")) in
  let* () = check "overflow before missing key" (S.expire ~condition:S.XX ~absolute:true ~seconds:true "missing" "-9223372036854776" original = Error (S.Expire_range "expireat")) in
  let* () = check "clock addition overflow" (S.expire ~condition:S.NX ~seconds:false "key" "9223372036854775807" shifted = Error (S.Expire_range "pexpire")) in
  let* reply, after = ok (S.expire ~condition:S.GT ~seconds:true "key" "3" shifted) in
  let* () = check "relative seconds scale the deadline" (reply = "1" && deadline after = Some 4000L) in
  let* reply, after = ok (S.expire ~condition:S.NX ~absolute:true ~seconds:true "key" "3" original) in
  let* () = check "absolute seconds scale the deadline" (reply = "1" && deadline after = Some 3000L) in
  let* reply, after = ok (S.expire ~condition:S.GT ~seconds:true "key" "1" shifted) in
  let* () = check "seconds rejection keeps the state" (reply = "0" && after = shifted) in
  let* expired = ok (S.advance "2001" volatile) in
  let* reply, after = ok (S.expire ~condition:S.NX ~seconds:true "key" "1" expired) in
  check "expired key stays missing" (reply = "0" && after = expired)

let () =
  let result = let* () = matrix () in boundaries () in
  Result.fold ~ok:(fun () -> Printf.printf "PASS CONDITIONAL-UNIT cases=%d\n" !checked)
    ~error:(fun message -> Printf.eprintf "FAIL CONDITIONAL-UNIT %s\n" message; exit 1) result
