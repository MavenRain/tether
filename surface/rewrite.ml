module S = Kanon_surface.Syntax
let ( let* ) = Result.bind
let all f xs = List.fold_right (fun x acc ->
  let* x = f x in let* xs = acc in Ok (x :: xs)) xs (Ok [])

(* Generated schema terms must not capture a user's local binder. *)
let binder_name protected name =
  if List.mem name protected || String.starts_with ~prefix:Constructors.prefix name then
    Error (Diagnostic.Reserved ("binder " ^ name)) else Ok ()

let rec spine acc = function
  | S.SApp (f, x) -> spine (x :: acc) f
  | S.SVar name -> Some name, acc
  | S.SNat _ | S.SProp | S.SType _ | S.SPrim _ | S.SUnit | S.SAuto
  | S.SPair _ | S.STuple _ | S.SSum _ | S.SProd _ | S.SProj _ | S.SInj _
  | S.SAbsurd _ | S.SFun _ | S.SArrow _ | S.SStar _ | S.SLet _ | S.SAnn _
  | S.SCase _ | S.SMatch _ -> None, acc

let command_key t =
  let name, args = spine [] t in
  let key = if name = Some "incr" then
      (match args with [_a; _g; key] -> Some key | _args -> None)
    else if name = Some "get" then
      (match args with [_a; _e; _g; key] -> Some key | _args -> None)
    else None in
  key |> Option.fold ~none:(Ok ()) ~some:(fun key ->
    let ctor, args = spine [] key in
    if ctor <> Some "keyBytes" then Ok () else
    match args with
    | [ty; _tag; _bytes] ->
        let valid = if name = Some "incr" then ty = S.SApp (S.SVar "Str", S.SVar "Int64")
          else let head, args = spine [] ty in head = Some "Str" && List.length args = 1 in
        if valid then Ok () else Error (Diagnostic.Wrongtype
          (if name = Some "incr" then "INCR requires Key (Str Int64)" else "GET requires a Str key"))
    | _args -> Ok ())

let declarations protected aliases decls =
  let rec term = function
    | S.SVar name -> Ok (S.SVar (Option.value (List.assoc_opt name aliases) ~default:name))
    | (S.SNat _ | S.SProp | S.SType _ | S.SPrim _ | S.SUnit | S.SAuto) as t -> Ok t
    | S.SPair (a, b) -> let* a = term a in let* b = term b in Ok (S.SPair (a, b))
    | S.STuple xs -> Result.map (fun xs -> S.STuple xs) (all term xs)
    | S.SSum xs -> Result.map (fun xs -> S.SSum xs) (all term xs)
    | S.SProd xs -> Result.map (fun xs -> S.SProd xs) (all term xs)
    | S.SProj (x, i) -> Result.map (fun x -> S.SProj (x, i)) (term x)
    | S.SInj (i, n, x) -> Result.map (fun x -> S.SInj (i, n, x)) (term x)
    | S.SAbsurd x -> Result.map (fun x -> S.SAbsurd x) (term x)
    | S.SApp (f, x) ->
        let* () = command_key (S.SApp (f, x)) in
        let* f = term f in let* x = term x in Ok (S.SApp (f, x))
    | S.SFun (bs, body) -> let* bs = all binder bs in let* body = term body in Ok (S.SFun (bs, body))
    | S.SArrow (b, cod) -> let* b = binder b in let* cod = term cod in Ok (S.SArrow (b, cod))
    | S.SStar (b, cod) -> let* b = binder b in let* cod = term cod in Ok (S.SStar (b, cod))
    | S.SLet (name, ty, value, body) ->
        let* () = binder_name protected name in
        let* ty = term ty in let* value = term value in let* body = term body in
        Ok (S.SLet (name, ty, value, body))
    | S.SAnn (x, ty) -> let* x = term x in let* ty = term ty in Ok (S.SAnn (x, ty))
    | S.SCase (x, mo, branches) ->
        let* x = term x in let* mo = optional motive mo in let* branches = all branch branches in
        Ok (S.SCase (x, mo, branches))
    | S.SMatch (x, mo, branches) ->
        let* x = term x in let* mo = optional motive mo in let* branches = all branch branches in
        Ok (S.SMatch (x, mo, branches))
  and binder (b : S.binder) =
    let* () = binder_name protected b.b_name in
    Result.map (fun b_ty -> { b with S.b_ty }) (term b.b_ty)
  and motive (m : S.motive) =
    let* _names = all (binder_name protected) (m.mo_self :: m.mo_idx) in
    Result.map (fun mo_body -> { m with S.mo_body }) (term m.mo_body)
  and field (f : S.field) =
    let* () = binder_name protected f.fd_name in
    Result.map (fun fd_ty -> { f with S.fd_ty }) (optional term f.fd_ty)
  and branch = function
    | S.BrLeg (i, bs, body) -> let* bs = all binder bs in let* body = term body in Ok (S.BrLeg (i, bs, body))
    | S.BrCtor (name, fs, body) -> let* fs = all field fs in let* body = term body in Ok (S.BrCtor (name, fs, body))
  and optional : 'a. ('a -> ('a, Diagnostic.t) result) -> 'a option -> ('a option, Diagnostic.t) result =
    fun f value -> Option.fold ~none:(Ok None) ~some:(fun x -> Result.map Option.some (f x)) value in
  let ctor (c : S.fam_ctor) = Result.map (fun fc_ty -> { c with S.fc_ty }) (term c.fc_ty) in
  let family (f : S.fam) =
    let* fm_params = all binder f.fm_params in let* fm_ty = term f.fm_ty in
    let* fm_ctors = all ctor f.fm_ctors in Ok { f with S.fm_params; fm_ty; fm_ctors } in
  let rec_def (d : S.rec_def) =
    let* rd_ty = term d.rd_ty in let* rd_body = term d.rd_body in Ok { d with S.rd_ty; rd_body } in
  all (function
    | S.DDef (name, ty, body) -> let* ty = term ty in let* body = term body in Ok (S.DDef (name, ty, body))
    | S.DAxiom (name, ty) -> Result.map (fun ty -> S.DAxiom (name, ty)) (term ty)
    | S.DMu fs -> Result.map (fun fs -> S.DMu fs) (all family fs)
    | S.DRec ds -> Result.map (fun ds -> S.DRec ds) (all rec_def ds)) decls
