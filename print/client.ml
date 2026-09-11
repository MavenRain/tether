let ( let* ) = Result.bind
let exports = ["emptyBytes"; "consBytes"; "bytesEmpty"; "bytesHead"; "bytesTail";
  "emptyWords"; "wordsEmpty"; "wordsHead"; "wordsTail"; "init"; "resume";
  "requestCode"; "requestArgs"; "requestBody"; "exitCode"]

(* Compile the shared static plan into a reactor. The selected reply stays
   opaque until the host formats it, including across later invocations. *)
let source (plan : Sh.plan) artifacts =
  let constants = ref [] in
  let literal text =
    let rec chunks bytes = if Seq.is_empty bytes then [] else
      String.of_seq (Seq.take 64 bytes) :: chunks (Seq.drop 64 bytes) in
    let parts = List.map (fun part ->
      let name = "tetherBytes" ^ string_of_int (List.length !constants) in
      constants := (name, part) :: !constants; name) (chunks (String.to_seq text)) in
    List.fold_right (fun part rest -> "bytesAppend " ^ part ^ " (" ^ rest ^ ")") parts "bytesNil" in
  let* calls = Lua.all (List.mapi (fun i name ->
    let* artifact = List.assoc_opt name artifacts
      |> Option.to_result ~none:("CLIENT-SCRIPT " ^ name) in
    Ok (i, artifact)) plan.invokes) in
  let call i = "tetherCall" ^ string_of_int i in
  let terminal saved = match plan.finish with
    | Sh.Answer _i -> "tetherWrite " ^ saved
    | Sh.Failure -> "tetherExit 4" in
  let after i saved = if i + 1 = List.length calls then terminal saved
    else call (i + 1) ^ " " ^ saved in
  let cases result query writing finished =
    "case state as current in TetherState return " ^ result ^ " with\n" ^
    String.concat "" (List.map (fun (i, a) -> "| " ^ call i ^ " saved => " ^ query i a ^ "\n") calls) ^
    "| tetherWrite body => " ^ writing ^ "\n| tetherExit result => " ^ finished ^ "\n" in
  let definition name ty args body = "\ndef " ^ name ^ " : " ^ ty ^ " := " ^ args ^ body in
  let state_arg = "fun (state : TetherState) =>\n" in
  let initial = if calls = [] then terminal "bytesNil" else call 0 ^ " bytesNil" in
  let valid = match plan.finish with
    | Sh.Failure -> true
    | Sh.Answer i -> i >= 0 && i < List.length calls in
  if not valid then Error "CLIENT-ANSWER invalid reply index" else
  let program = "mu TetherState : Type 0 with\n" ^ String.concat ""
    (List.map (fun (i, _a) -> "| " ^ call i ^ " : Bytes -> TetherState\n") calls) ^
    "| tetherWrite : Bytes -> TetherState\n| tetherExit : Nat -> TetherState\n" ^
    definition "init" "Words -> TetherState" "fun (args : Words) => " initial ^
    definition "resume" "TetherState -> Nat -> Bytes -> TetherState"
      "fun (state : TetherState) (status : Nat) (answer : Bytes) =>\n"
      (cases "TetherState" (fun i _a ->
        let saved = match plan.finish with
          | Sh.Answer n -> if i = n then "answer" else "saved"
          | Sh.Failure -> "saved" in
        "(case (natEq status 0) with\n| 0 (bad : prod ()) => tetherExit 4\n" ^
        "| 1 (ok : prod ()) => " ^ after i saved ^ ")") "tetherExit 0" "tetherExit result") ^
    definition "requestCode" "TetherState -> Nat" state_arg
      (cases "Nat" (fun _i _a -> "10") "11" "0") ^
    definition "requestArgs" "TetherState -> Words" state_arg
      (cases "Words" (fun _i a ->
        let keys = List.map (fun ns -> "b\"" ^ String.concat ""
          (List.map (Printf.sprintf "\\x%02x") ns) ^ "\"") a.Lua.keys in
        List.fold_right (fun text rest -> "wordsCons " ^ text ^ " (" ^ rest ^ ")")
          (Transport.literal a.sha1 :: keys) "wordsNil") "wordsNil" "wordsNil") ^
    definition "requestBody" "TetherState -> Bytes" state_arg
      (cases "Bytes" (fun _i a -> literal a.Lua.body) "body" "bytesNil") ^
    definition "exitCode" "TetherState -> Nat" state_arg
      (cases "Nat" (fun _i _a -> "4") "4" "result") in
  let constants = List.rev !constants in
  Ok (String.concat "\n" (List.map (fun (name, _text) ->
    "def " ^ name ^ " : Bytes := bytesNil") constants) ^ "\n" ^ program, constants)

let emit ~budget ~reactor plan artifacts =
  let* source, constants = source plan artifacts |> Result.map_error (fun e -> Kanon_kernel.Error.Mismatch e) in
  let* globals, rows = Kanon_surface.Elab.check_in ~budget Kanon_kernel.Global.initial
    (reactor ^ "\n" ^ source) in
  let* rows = Kanon_kernel.Erase.program ~budget globals rows in
  let* rows = Transport.byte_constants constants rows in
  Kanon_wasm.Emit.reactor rows ~exports
