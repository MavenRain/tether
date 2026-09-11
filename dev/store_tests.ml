module S = Tether_store.Store
module I = Tether_store.Interp
let ( let* ) = Result.bind
let require passed message = if passed then Ok () else Error message
let run () =
  let cases = ["0", "1"; "-1", "0"; "-10", "-9"; "9", "10";
    "9007199254740992", "9007199254740993";
    "9223372036854775806", "9223372036854775807";
    "-9223372036854775808", "-9223372036854775807"] in
  let* () = List.fold_left (fun acc (initial, expected) -> let* () = acc in
    let store = S.put "k" (S.Str initial) S.empty in
    let* actual, after = S.incr "k" store |> Result.map_error S.message in
    require (actual = expected && S.get "k" after = Ok (Some expected) &&
      S.get "k" store = Ok (Some initial)) "STORE integer/immutability") (Ok ()) cases in
  let* () = List.fold_left (fun acc value -> let* () = acc in
    require (S.incr "k" (S.put "k" (S.Str value) S.empty) = Error S.Not_integer) "STORE invalid integer")
    (Ok ()) [""; "01"; "-0"; "+1"; "1.5"; " 1"; "0xff"; "1_0"; "9223372036854775808"] in
  let* () = require (S.incr "k" (S.put "k" (S.Str "9223372036854775807") S.empty) = Error S.Overflow)
    "STORE overflow" in
  let* () = List.fold_left (fun acc value -> let* () = acc in
    let store = S.put "k" value S.empty in
    require (S.get "k" store = Error S.Wrong_type && S.incr "k" store = Error S.Wrong_type)
      "STORE wrong type") (Ok ()) [S.Hash []; S.List []; S.Set []; S.ZSet []; S.Stream []] in
  let* value, _store = S.incr "k" S.empty |> Result.map_error S.message in
  let* () = require (value = "1" && S.get "k" S.empty = Ok None) "STORE missing" in
  let* () = require (I.text (I.bytes I.octets) = Ok I.octets) "STORE all bytes" in
  let budget = Kanon_kernel.Budget.of_poll (fun () -> true) in
  let rows = ["main", Kanon_kernel.Erase.Code [Kanon_kernel.Eterm.KFun
    (Kanon_kernel.Eterm.Fid "main", [], Kanon_kernel.Eterm.RI31, Kanon_kernel.Eterm.KErased)]] in
  require (I.run ~budget rows ~entry:"main" S.empty = Error "STORE-BUDGET") "STORE budget"
let () = run () |> Result.fold
  ~ok:(fun () -> print_endline "PASS STORE-UNIT cases=25")
  ~error:(fun e -> prerr_endline e; exit 1)
