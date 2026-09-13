module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let require condition reason = if condition then Ok () else Error ("LISTS-UNIT " ^ reason)
let fold f xs = List.fold_left (fun acc x -> let* n = acc in let* () = f x in Ok (n + 1)) (Ok 0) xs
let list values = S.put "k" (S.List values) S.empty
let same a b = S.Keys.bindings a = S.Keys.bindings b
let hex s = String.concat "" (List.of_seq (Seq.map (fun c -> Printf.sprintf "%02x" (Char.code c)) (String.to_seq s)))
let rec term = function
  | I.Data (tid, tag, xs) -> E.KTag (tid, tag, List.map term xs)
  | I.Literal l -> E.KLit l
  | I.Fields _ | I.Closure _ | I.Erased -> E.KErased
let bytes s = term (I.bytes s)
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
let run () =
  let samples = [
    19, [bytes "m"], S.empty, I.Int "1", list ["m"], "left create";
    20, [bytes "m"], S.empty, I.Int "1", list ["m"], "right create";
    19, [bytes "m"], list ["a"; "z"], I.Int "3", list ["m"; "a"; "z"], "left push order";
    20, [bytes "m"], list ["a"; "z"], I.Int "3", list ["a"; "z"; "m"], "right push order";
    19, [bytes "m"], list ["m"], I.Int "2", list ["m"; "m"], "duplicates retained";
    21, [], S.empty, I.Nil, S.empty, "missing left pop";
    22, [], S.empty, I.Nil, S.empty, "missing right pop";
    21, [], list ["a"; "m"; "z"], I.Bulk "a", list ["m"; "z"], "left pop order";
    22, [], list ["a"; "m"; "z"], I.Bulk "z", list ["a"; "m"], "right pop order";
    21, [], list ["m"], I.Bulk "m", S.empty, "left deletes last key";
    22, [], list ["m"], I.Bulk "m", S.empty, "right deletes last key";
    23, [], S.empty, I.Int "0", S.empty, "missing length";
    23, [], list ["m"; "m"; "z"], I.Int "3", list ["m"; "m"; "z"], "length includes duplicates"] in
  let* interpreted = fold (fun (tag, args, before, expected, after, name) ->
    let before = S.put "other" (S.Str "kept") before in
    let* reply, actual = execute tag args before in
    require (reply = expected && same actual (S.put "other" (S.Str "kept") after)) name) samples in
  let wrong_types = [S.Str "old"; S.Hash ["f", "v"]; S.Set ["m"]; S.ZSet ["m", "1"]; S.Stream []] in
  let operations = [19, [bytes "m"], (fun s -> Result.map (fun _ -> ()) (S.push S.Left "k" "m" s)), "lpush";
    20, [bytes "m"], (fun s -> Result.map (fun _ -> ()) (S.push S.Right "k" "m" s)), "rpush";
    21, [], (fun s -> Result.map (fun _ -> ()) (S.pop S.Left "k" s)), "lpop";
    22, [], (fun s -> Result.map (fun _ -> ()) (S.pop S.Right "k" s)), "rpop";
    23, [], (fun s -> Result.map (fun _ -> ()) (S.llen "k" s)), "llen"] in
  let* wrong = fold (fun (tag, args, operation, name, value) ->
    let before = S.put "k" value (S.put "other" (S.Str "kept") S.empty) in
    let* () = require (operation before = Error S.Wrong_type
      && execute tag args before = Error (S.message S.Wrong_type)) (name ^ " wrong type stops client") in
    let* reply, after = execute ~expose:true tag args before in
    require (reply = I.Status (S.message S.Wrong_type) && same before after) (name ^ " err preserves store"))
    (List.concat_map (fun (tag, args, f, name) -> List.map (fun v -> tag, args, f, name, v) wrong_types) operations) in
  let payloads = [""; "\000"; "\255"; "\000\255\n\"$(touch forbidden)\\"; "1"; "01"; "-0"; "0"] in
  let* binary = fold (fun (push, pop, value) ->
    let* count, before = execute push [bytes value] S.empty in
    let* reply, after = execute pop [] before in
    require (count = I.Int "1" && reply = I.Bulk value && same after S.empty)
      (Printf.sprintf "binary interpreter roundtrip push=%d pop=%d payload=%s" push pop (hex value)))
    (List.concat_map (fun value -> [19, 22, value; 20, 21, value]) payloads) in
  let* queue =
    let* _, one = S.push S.Right "k" "first" S.empty |> Result.map_error S.message in
    let* _, two = S.push S.Right "k" "second" one |> Result.map_error S.message in
    let* first, one = S.pop S.Left "k" two |> Result.map_error S.message in
    let* second, empty = S.pop S.Left "k" one |> Result.map_error S.message in
    let* missing, unchanged = S.pop S.Left "k" empty |> Result.map_error S.message in
    let* () = require (first = Some "first" && second = Some "second" && missing = None
      && same empty S.empty && same empty unchanged) "FIFO drain" in Ok 1 in
  let total = interpreted + wrong + binary + queue in
  let* () = require (total = 55) (Printf.sprintf "expected 55 cases, counted %d" total) in
  Ok total
let () = run () |> Result.fold
  ~ok:(fun count -> Printf.printf "PASS LISTS-UNIT cases=%d\n" count)
  ~error:(fun e -> prerr_endline ("FAIL " ^ e); exit 1)
