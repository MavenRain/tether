open Kanon_kernel
let ( let* ) = Result.bind
let hex text = String.concat "" (List.of_seq
  (Seq.map (fun c -> Printf.sprintf "%02x" (Char.code c)) (String.to_seq text)))
let literal text = "b\"" ^ String.concat "" (List.of_seq
  (Seq.map (fun c -> Printf.sprintf "\\x%02x" (Char.code c)) (String.to_seq text))) ^ "\""

(* Retain the checked tag index while requiring Reply as the result. *)
let entry ~budget globals name =
  let* definition = Global.find_def name globals
    |> Option.to_result ~none:(Error.Unbound ("LUA-ENTRY " ^ name)) in
  let* shape = match definition.ty with
    | Term.Lan (shape, _diagram) ->
        if Shape.family shape = Some "Script" then Ok shape
        else Error (Error.Mismatch "LUA-ENTRY expected Script Reply")
    | Term.Var _ | Term.Univ _ | Term.Ran _ | Term.In _ | Term.Elim _
    | Term.Sec _ | Term.Out _ | Term.Let _ | Term.Ann _ | Term.Global _
    | Term.Lit _ | Term.Auto -> Error (Error.Mismatch "LUA-ENTRY expected Script Reply") in
  let reply = Term.Lan (Shape.SMu ("Reply", []), Term.Sec (Shape.SColl 0, [])) in
  let ty = Term.Lan (shape, Term.Sec (Shape.SColl 1, [Rules.leg_of reply])) in
  Check.check_decls ~budget globals [{ Check.d_name = "tetherLuaEntryCheck";
    d_kind = Check.Definition; d_ty = ty; d_body = Some (Term.Global name) }]
  |> Result.map (fun _rows -> ())

(* These exports are the Stage C byte carrier; the Client reactor is Stage E. *)
let wasm ~budget ~reactor (artifact : Lua.artifact) =
  let source = reactor ^ "\ndef requestBody : Bytes := " ^ literal artifact.body ^
    "\ndef scriptSha1 : Bytes := " ^ literal artifact.sha1 in
  let* globals, rows = Kanon_surface.Elab.check_in ~budget Global.initial source in
  let* rows = Erase.program ~budget globals rows in
  Kanon_wasm.Emit.reactor rows
    ~exports:["requestBody"; "scriptSha1"; "bytesEmpty"; "bytesHead"; "bytesTail"]

(* Lower byte payloads directly to the carried Bytes representation. The
   generated reactor is checked with typed empty slots first; this total
   substitution avoids elaborating thousands of nested constructor calls. *)
let byte_constants constants rows =
  let module E = Eterm in
  let tid = E.Tid "mu<Bytes>" in
  Lua.all (List.map (fun (name, entry) -> List.assoc_opt name constants
    |> Option.fold ~none:(Ok (name, entry)) ~some:(fun text ->
        let bytes = List.fold_right (fun c rest -> E.KTag (tid, 1,
          [E.KLit (Literal.LInt (Bignum.of_int (Char.code c))); rest]))
          (List.of_seq (String.to_seq text)) (E.KTag (tid, 0, [])) in
        let* decls = match entry with
          | Erase.Code decls -> Lua.all (List.map (function
              | E.KRec group -> Ok (E.KRec group)
              | E.KFun (E.Fid n, [], E.RUnion t, _empty) when n = name && t = tid ->
                  Ok (E.KFun (E.Fid n, [], E.RUnion t, bytes))
              | E.KFun _ -> Error (Error.Mismatch "CLIENT-BYTES slot type")) decls)
          | Erase.Dropped | Erase.Postulate _ -> Error (Error.Mismatch "CLIENT-BYTES slot") in
        Ok (name, Erase.Code decls))) rows)
