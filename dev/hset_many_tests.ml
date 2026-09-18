module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let store result = Result.map_error S.message result
let require condition reason = if condition then Ok () else Error ("HSET-MANY-UNIT " ^ reason)
let fold f xs = List.fold_left (fun acc x -> let* n = acc in let* () = f x in Ok (n + 1)) (Ok 0) xs
let rec term = function
  | I.Data (tid, tag, xs) -> E.KTag (tid, tag, List.map term xs)
  | I.Literal l -> E.KLit l
  | I.Fields _ | I.Closure _ | I.Erased -> E.KErased
let bytes s = term (I.bytes s)
let rec arguments (field, value) = function
  | [] -> E.KTag (E.Tid "mu<BulkPairs>", 0, [bytes field; bytes value])
  | next :: rest -> E.KTag (E.Tid "mu<BulkPairs>", 1, [bytes field; bytes value; arguments next rest])
let execute ?(expose=false) args before =
  let key = E.KTag (E.Tid "mu<Key>", 0, [bytes "k"]) in
  let script = E.KTag (E.Tid "mu<Script>", 58, key :: args @ [E.KClos (E.Fid "pure", 1, [])]) in
  let client = E.KTag (E.Tid "mu<Client>", 1, [script; E.KClos (E.Fid "done", 1, [])]) in
  let fn name ps body = E.KFun (E.Fid name, ps, E.RI31, body) in
  let answer = if expose then E.KCase (E.Tid "mu<Reply>", E.KVar 0,
    [{E.tag=4; arity=1; body=E.KTag (E.Tid "mu<Reply>", 3, [E.KVar 0])}]) else E.KVar 0 in
  let rows = ["main", Kanon_kernel.Erase.Code [fn "main" [] client;
    fn "pure" [E.RI31] (E.KTag (E.Tid "mu<Script>", 0, [answer]));
    fn "done" [E.RI31] (E.KTag (E.Tid "mu<Client>", 0, [E.KVar 0]))]] in
  I.run ~budget:(Kanon_kernel.Budget.of_poll (fun () -> false)) rows ~entry:"main" before
let run () =
  let many = List.init 129 (fun i -> Printf.sprintf "v%03d" i, string_of_int i) in
  let cases = [
    None, ("a", "A"), [], ["a", "A"], "1";
    None, ("a", "A"), ["a", "middle"; "b", "B"; "a", "last"], ["a", "last"; "b", "B"], "2";
    Some ["a", "old"; "kept", "K"], ("a", "A"), ["b", "B"; "a", "last"], ["a", "last"; "b", "B"; "kept", "K"], "1";
    Some ["a", "old"], ("a", "old"), ["a", "old"], ["a", "old"], "0";
    Some ["a", "old"], ("a", "A"), [], ["a", "A"], "0";
    None, ("", ""), ["a", "A"; "", "last"], ["", "last"; "a", "A"], "2";
    Some ["seed", "kept"], (I.octets, "\000"), ["\000", I.octets; I.octets, "last"], ["seed", "kept"; I.octets, "last"; "\000", I.octets], "2";
    Some ["01", "001"], ("1", "9007199254740993"), ["01", "-9223372036854775808"], ["01", "-9223372036854775808"; "1", "9007199254740993"], "1";
    None, ("v000", "old"), many, many, "129";
    Some ["v000", "old"], ("v000", "0"), many, many, "128";
    Some many, ("v000", "0"), many, many, "0";
    Some ["a", "A"], ("b", "B"), ["c", "C"], ["a", "A"; "b", "B"; "c", "C"], "2"] in
  let* values = fold (fun (initial, (field, value), rest, expected, count, expiring) ->
    let before = S.put "other" (S.Str "kept") S.empty in
    let* _, before = store (S.expire ~seconds:false "other" "9000" before) in
    let before = Option.fold ~none:before ~some:(fun xs -> S.put "k" (S.Hash xs) before) initial in
    let* before = if expiring then Result.map snd (store (S.expire ~seconds:false "k" "5000" before)) else Ok before in
    let wanted = S.put "k" (S.Hash (List.sort compare expected)) before in
    let* actual = store (S.hset ~rest "k" field value before) in
    let* () = require (actual = (count, wanted)) "store count and complete state" in
    let* reply, after = execute [arguments (field, value) rest] before in
    require (reply = I.Int count && after = wanted) "interpreter count and complete state")
    (List.concat_map (fun (a, b, c, d, e) -> List.map (fun ttl -> a, b, c, d, e, ttl) [false; true]) cases) in
  let* errors = fold (fun value ->
    let before = S.put "k" value (S.put "other" (S.Str "kept") S.empty) in
    let* _, before = store (S.expire ~seconds:false "k" "5000" before) in
    let* () = require (S.hset ~rest:["b", "B"] "k" "a" "A" before = Error S.Wrong_type) "store wrong type" in
    let* () = require (execute [arguments ("a", "A") ["b", "B"]] before = Error (S.message S.Wrong_type)) "error stops client" in
    let* reply, after = execute ~expose:true [arguments ("a", "A") ["b", "B"]] before in
    require (reply = I.Status (S.message S.Wrong_type) && after = before) "error preserves complete state")
    [S.Str "old"; S.Set ["m"]; S.List ["m"]; S.ZSet ["m", "1"]; S.Stream []] in
  let bad tag xs = E.KTag (E.Tid "mu<BulkPairs>", tag, xs) in
  let fields = E.KTag (E.Tid "mu<BulkArgs>", 0, [bytes "a"]) in
  let* shapes = fold (fun (args, expected) ->
    require (execute args S.empty = Error expected) "malformed operand refusal") [
      [], "STORE-SCRIPT-COMMAND"; [bytes "a"], "STORE-SCRIPT-COMMAND";
      [fields], "STORE-SCRIPT-COMMAND"; [arguments ("a", "A") []; arguments ("b", "B") []], "STORE-SCRIPT-COMMAND";
      [bad 2 [bytes "a"; bytes "A"]], "STORE-BULK-PAIRS"; [bad 0 []], "STORE-BULK-PAIRS";
      [bad 0 [bytes "a"]], "STORE-BULK-PAIRS"; [bad 0 [bytes "a"; bytes "A"; bytes "b"]], "STORE-BULK-PAIRS";
      [bad 0 [E.KErased; bytes "A"]], "STORE-BYTES"; [bad 0 [bytes "a"; E.KErased]], "STORE-BYTES";
      [bad 1 [bytes "a"; bytes "A"; fields]], "STORE-BULK-PAIRS";
      [bad 1 []], "STORE-BULK-PAIRS";
      [bad 1 [bytes "a"; bytes "A"; bad 0 []]], "STORE-BULK-PAIRS"] in
  let before = S.put "k" (S.Str "wrong") (S.put "other" (S.Str "kept") S.empty) in
  let* _, expiring = store (S.expire ~seconds:false "k" "1" before) in
  let* expired = store (S.advance "2" expiring) in
  let* reply, after = execute [arguments ("a", "A") []] expired in
  let* () = require (reply = I.Int "1" && after = S.put "k" (S.Hash ["a", "A"]) expired) "expired key is recreated without expiry" in
  let count = values + errors + shapes + 1 in
  let* () = require (count = 43) "case inventory" in Ok count
let () = run () |> Result.fold
  ~ok:(fun count -> Printf.printf "PASS HSET-MANY-UNIT cases=%d\n" count)
  ~error:(fun e -> prerr_endline ("FAIL " ^ e); exit 1)
