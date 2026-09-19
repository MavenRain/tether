module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let store result = Result.map_error S.message result
let require condition reason = if condition then Ok () else Error ("LIST-CONDITIONAL-UNIT " ^ reason)
let fold f xs = List.fold_left (fun acc x -> let* n = acc in let* () = f x in Ok (n + 1)) (Ok 0) xs
let rec term = function
  | I.Data (tid, tag, xs) -> E.KTag (tid, tag, List.map term xs)
  | I.Literal l -> E.KLit l
  | I.Fields _ | I.Closure _ | I.Erased -> E.KErased
let bytes s = term (I.bytes s)
let rec arguments first = function
  | [] -> E.KTag (E.Tid "mu<BulkArgs>", 0, [bytes first])
  | next :: rest -> E.KTag (E.Tid "mu<BulkArgs>", 1, [bytes first; arguments next rest])
let execute ?(expose=false) tag args before =
  let key = E.KTag (E.Tid "mu<Key>", 0, [bytes "k"]) in
  let script = E.KTag (E.Tid "mu<Script>", tag, key :: args @ [E.KClos (E.Fid "pure", 1, [])]) in
  let client = E.KTag (E.Tid "mu<Client>", 1, [script; E.KClos (E.Fid "done", 1, [])]) in
  let fn name ps body = E.KFun (E.Fid name, ps, E.RI31, body) in
  let answer = if expose then E.KCase (E.Tid "mu<Reply>", E.KVar 0,
    [{E.tag=4; arity=1; body=E.KTag (E.Tid "mu<Reply>", 3, [E.KVar 0])}]) else E.KVar 0 in
  let rows = ["main", Kanon_kernel.Erase.Code [fn "main" [] client;
    fn "pure" [E.RI31] (E.KTag (E.Tid "mu<Script>", 0, [answer]));
    fn "done" [E.RI31] (E.KTag (E.Tid "mu<Client>", 0, [E.KVar 0]))]] in
  I.run ~budget:(Kanon_kernel.Budget.of_poll (fun () -> false)) rows ~entry:"main" before
let run_side (side, tag, bulk) =
  let operand first rest = if bulk then [arguments first rest] else [bytes first] in
  let cases = [
    None, "a", [];
    None, "a", ["b"; "c"];
    Some ["old"; "tail"], "a", ["b"; "c"];
    Some ["old"], "dup", ["dup"; ""];
    Some [""], "", [""; "a"];
    Some ["seed"], I.octets, ["\000"; I.octets];
    Some ["seed"], "9007199254740993", [];
    None, "first", List.init 129 string_of_int] in
  let* values = fold (fun (initial, first, rest) ->
    let rest = if bulk then rest else [] in
    let before = S.put "other" (S.Str "kept") S.empty in
    let before = Option.fold ~none:before ~some:(fun xs -> S.put "k" (S.List xs) before) initial in
    let* _, before = store (S.expire ~seconds:false "k" "5000" before) in
    let initial = Option.value ~default:[] initial in
    let expected = if initial = [] then [] else match side with S.Left -> List.rev (first :: rest) @ initial | S.Right -> initial @ (first :: rest) in
    let wanted = if initial = [] then before else S.put "k" (S.List expected) before in
    let count = string_of_int (List.length expected) in
    let* actual = store (S.push ~xx:true ~rest side "k" first before) in
    let* () = require (actual = (count, wanted)) "store order, count and complete state" in
    let* reply, after = execute tag (operand first rest) before in
    require (reply = I.Int count && after = wanted) "interpreter order, count and complete state") cases in
  let* errors = fold (fun value ->
    let before = S.put "k" value (S.put "other" (S.Str "kept") S.empty) in
    let* _, before = store (S.expire ~seconds:false "k" "5000" before) in
    let* () = require (S.push ~xx:true ~rest:["b"; "c"] side "k" "a" before = Error S.Wrong_type) "store wrong type" in
    let* () = require (execute tag (operand "a" ["b"; "c"]) before = Error (S.message S.Wrong_type)) "error stops client" in
    let* reply, after = execute ~expose:true tag (operand "a" ["b"; "c"]) before in
    require (reply = I.Status (S.message S.Wrong_type) && after = before) "error preserves complete state")
    [S.Str "old"; S.Hash ["f", "v"]; S.Set ["m"]; S.ZSet ["m", "1"]; S.Stream []] in
  let bad tag xs = E.KTag (E.Tid "mu<BulkArgs>", tag, xs) in
  let invalid = if bulk then [
      [], "STORE-SCRIPT-COMMAND"; [bytes "a"], "STORE-SCRIPT-COMMAND";
      [arguments "a" []; arguments "b" []], "STORE-SCRIPT-COMMAND";
      [bad 2 [bytes "a"]], "STORE-BULK-ARGS"; [bad 0 []], "STORE-BULK-ARGS";
      [bad 0 [E.KErased]], "STORE-BYTES"] else [
      [], "STORE-SCRIPT-COMMAND"; [bytes "a"; bytes "b"], "STORE-SCRIPT-COMMAND";
      [arguments "a" []], "STORE-SCRIPT-COMMAND"] in
  let* shapes = fold (fun (args, expected) ->
    require (execute tag args S.empty = Error expected) "malformed operand refusal") invalid in
  let before = S.put "k" (S.Hash ["f", "v"]) (S.put "other" (S.Str "kept") S.empty) in
  let* _, expiring = store (S.expire ~seconds:false "k" "1" before) in
  let* expired = store (S.advance "2" expiring) in
  let* reply, after = execute tag (operand "a" []) expired in
  let* () = require (reply = I.Int "0" && after = expired) "expired key stays absent" in
  Ok (values + errors + shapes + 1)
let run () =
  let* left = run_side (S.Left, 61, false) in
  let* right = run_side (S.Right, 62, false) in
  let* left_bulk = run_side (S.Left, 63, true) in
  let* right_bulk = run_side (S.Right, 64, true) in
  let count = left + right + left_bulk + right_bulk in
  let* () = require (count = 74) "case inventory" in Ok count
let () = run () |> Result.fold
  ~ok:(fun count -> Printf.printf "PASS LIST-CONDITIONAL-UNIT cases=%d\n" count)
  ~error:(fun e -> prerr_endline ("FAIL " ^ e); exit 1)
