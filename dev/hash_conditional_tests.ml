module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let require condition reason = if condition then Ok () else Error ("HASH-CONDITIONAL-UNIT " ^ reason)
let fold f xs = List.fold_left (fun acc x -> let* n = acc in let* () = f x in Ok (n + 1)) (Ok 0) xs
let base = S.put "other" (S.Str "kept") { S.empty with now = 1000L; deadlines = S.Keys.singleton "other" 9000L }
let hash fields = S.put "k" (S.Hash fields) base
let expiring store = { store with S.deadlines = S.Keys.add "k" 7000L store.S.deadlines }
let rec term = function
  | I.Data (tid, tag, xs) -> E.KTag (tid, tag, List.map term xs)
  | I.Literal l -> E.KLit l
  | I.Fields _ | I.Closure _ | I.Erased -> E.KErased
let bytes s = term (I.bytes s)
let execute ?(recover = false) tag args before =
  let key = E.KTag (E.Tid "mu<Key>", 0, [bytes "k"]) in
  let script = E.KTag (E.Tid "mu<Script>", tag, key :: args @ [E.KClos (E.Fid "pure", 1, [])]) in
  let client = E.KTag (E.Tid "mu<Client>", 1, [script; E.KClos (E.Fid "done", 1, [])]) in
  let answer = if recover then E.KTag (E.Tid "mu<Reply>", 3, [bytes "caught"]) else E.KVar 0 in
  let fn name ps body = E.KFun (E.Fid name, ps, E.RI31, body) in
  let rows = ["main", Kanon_kernel.Erase.Code [fn "main" [] client;
    fn "pure" [E.RI31] (E.KTag (E.Tid "mu<Script>", 0, [answer]));
    fn "done" [E.RI31] (E.KTag (E.Tid "mu<Client>", 0, [E.KVar 0]))]] in
  I.run ~budget:(Kanon_kernel.Budget.of_poll (fun () -> false)) rows ~entry:"main" before
let run () =
  let inserts = [
    "f", "new", base, "1", hash ["f", "new"];
    "f", "new", hash ["other", "kept"], "1", hash ["f", "new"; "other", "kept"];
    "f", "new", hash ["f", "old"; "other", "kept"], "0", hash ["f", "old"; "other", "kept"];
    "f", "new", hash ["f", ""], "0", hash ["f", ""];
    "f", "new", hash ["f", "new"], "0", hash ["f", "new"];
    "", "", base, "1", hash ["", ""];
    "", "new", hash ["", ""], "0", hash ["", ""];
    "\000\255", I.octets, base, "1", hash ["\000\255", I.octets];
    "\000\255", "new", hash ["\000\255", I.octets], "0", hash ["\000\255", I.octets];
    "f", "new", expiring (hash ["other", "kept"]), "1", expiring (hash ["f", "new"; "other", "kept"]);
    "f", "new", expiring (hash ["f", ""]), "0", expiring (hash ["f", ""])] in
  let* inserted = fold (fun (field, value, before, count, after) ->
    let* actual, state = S.hset ~nx:true "k" field value before |> Result.map_error S.message in
    let* () = require (actual = count && state = after) "conditional insert and complete state" in
    let* reply, state = execute 59 [bytes field; bytes value] before in
    require (reply = I.Int count && state = after) "interpreter conditional insert") inserts in
  let lengths = [
    "f", base, "0"; "f", hash ["other", "kept"], "0";
    "f", hash ["f", ""], "0"; "f", hash ["f", "hello"], "5";
    "", hash ["", "x"], "1"; "f", hash ["f", "\195\169\240\159\153\130"], "6";
    "\000\255", hash ["\000\255", I.octets], "256";
    "f", expiring (hash ["f", "\000\255\000"]), "3";
    "f", expiring (hash ["other", "kept"]), "0"] in
  let* measured = fold (fun (field, before, expected) ->
    let* actual = S.hstrlen "k" field before |> Result.map_error S.message in
    let* () = require (actual = expected) "byte length" in
    let* reply, state = execute 60 [bytes field] before in
    require (reply = I.Int expected && state = before) "interpreter length and complete state") lengths in
  let wrong_types = [S.Str "old"; S.List ["x"]; S.Set ["x"]; S.ZSet ["x", "1"]; S.Stream ["f", "v"]] in
  let* faults = fold (fun value ->
    let before = expiring (S.put "k" value base) in
    let* () = require (S.hset ~nx:true "k" "f" "v" before = Error S.Wrong_type
      && S.hstrlen "k" "f" before = Error S.Wrong_type) "wrong type" in
    let* _ = fold (fun (tag, args) ->
      let* () = require (execute tag args before = Error (S.message S.Wrong_type)) "error stops client" in
      let* reply, state = execute ~recover:true tag args before in
      require (reply = I.Status "caught" && state = before) "caught error preserves complete state")
      [59, [bytes "f"; bytes "v"]; 60, [bytes "f"]] in Ok ()) wrong_types in
  let* expired = S.advance "6001" (expiring (hash ["f", "old"])) |> Result.map_error S.message in
  let* () = require (S.hstrlen "k" "f" expired = Ok "0") "expired length" in
  let* count, recreated = S.hset ~nx:true "k" "f" "new" expired |> Result.map_error S.message in
  let* () = require (count = "1" && S.hget "k" "f" recreated = Ok (Some "new")
    && not (S.Keys.mem "k" recreated.deadlines)) "expired insert is persistent" in
  let* malformed = fold (fun (tag, args) -> require (execute tag args base = Error "STORE-SCRIPT-COMMAND") "malformed operands")
    [59, []; 59, [bytes "f"]; 60, []; 60, [bytes "f"; bytes "v"];
     59, [bytes "f"; E.KTag (E.Tid "mu<Signed64>", 0, [bytes "1"])]] in
  Ok (inserted + measured + faults + malformed + 2)
let () = run () |> Result.fold
  ~ok:(fun count -> Printf.printf "PASS HASH-CONDITIONAL-UNIT cases=%d\n" count)
  ~error:(fun error -> prerr_endline ("FAIL " ^ error); exit 1)
