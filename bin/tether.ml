module D = Tether_surface.Diagnostic
module P = Tether_print
module K = Kanon_kernel
module I = Tether_store.Interp
let ( let* ) = Result.bind
let kernel result = Result.map_error (fun e -> D.Kernel e) result
let printer result = Result.map_error (fun e -> D.Syntax e) result
let read path =
  print_endline ("READ " ^ path); flush stdout;
  let* header = In_channel.input_line stdin |> Option.to_result ~none:(D.Read path) in
  let* size = int_of_string_opt header |> Option.to_result ~none:(D.Read path) in
  if size < 0 || size > 1048576 then Error (D.Read path) else
  In_channel.really_input_string stdin size |> Option.to_result ~none:(D.Read path)
let entry ~budget checked name =
  let reply = K.Term.Lan (K.Shape.SMu ("Reply", []), K.Term.Sec (K.Shape.SColl 0, [])) in
  let ty = K.Term.Lan (K.Shape.SMu ("Client", []), K.Term.Sec (K.Shape.SColl 1, [K.Rules.leg_of reply])) in
  kernel (K.Check.check_decls ~budget checked.Tether_surface.Elab.globals
    [{ K.Check.d_name = "tetherDriverEntryCheck"; d_kind = K.Check.Definition;
       d_ty = ty; d_body = Some (K.Term.Global name) }]) |> Result.map (fun _rows -> ())
let rec reply = function
  | I.Nil -> "null"
  | I.Int s -> "int:" ^ P.Transport.hex s
  | I.Bulk s -> "bulk:" ^ P.Transport.hex s
  | I.Status s -> "status:" ^ P.Transport.hex s
  | I.Err s -> "error:" ^ P.Transport.hex s
  | I.Array rs -> "array:[" ^ String.concat "," (List.map reply rs) ^ "]"
let emit ~budget ~reactor checked rows name =
  let* plan = printer (P.Sh.plan ~budget rows ~entry:name) in
  let* artifacts = P.Lua.all (List.map (fun name ->
    let* () = kernel (P.Transport.entry ~budget checked.Tether_surface.Elab.globals name) in
    let* a = printer (P.Lua.emit rows ~entry:name) in Ok (name, a))
    (List.sort_uniq String.compare plan.invokes)) in
  let* shell = printer (P.Sh.emit plan artifacts) in
  let* wasm = kernel (P.Client.emit ~budget ~reactor plan artifacts) in
  print_endline ("SH " ^ P.Transport.hex shell);
  print_endline ("WASM " ^ P.Transport.hex wasm);
  let answer = match plan.P.Sh.finish with P.Sh.Answer i -> i | P.Sh.Failure -> -1 in
  Printf.printf "CLIENT %d%s\n" answer (String.concat "" (List.map (fun n -> " " ^ n) plan.invokes));
  List.iter (fun (name, a) ->
    Printf.printf "SCRIPT %s %s %s%s\n" name a.P.Lua.sha1 (P.Transport.hex a.body)
      (String.concat "" (List.map (fun key -> " " ^ String.concat ""
        (List.map (Printf.sprintf "%02x") key)) a.keys))) artifacts;
  Ok ()
let run mode path name fuel =
  let* fuel = int_of_string_opt fuel |> Option.to_result ~none:(D.Syntax "invalid fuel") in
  if fuel < 0 then Error (D.Syntax "invalid fuel") else
  let remaining = ref fuel in
  let budget = K.Budget.of_poll (fun () -> if !remaining = 0 then true else (decr remaining; false)) in
  let* reactor = read "@reactor" in let* redis = read "@redis" in
  let passes = ref K.Global.StringMap.empty in
  let observe _stage names = if mode = "passes" then List.iter (fun name ->
    passes := K.Global.StringMap.update name (fun prior ->
      Some (1 + Option.value ~default:0 prior)) !passes) names in
  let* checked = Tether_surface.Elab.check_observed ~observe ~budget ~read ~path ~reactor ~redis in
  if mode = "check" || mode = "passes" then (
    K.Global.StringMap.iter (fun name count ->
      Printf.printf "PASSES def=%s walks=%d class=surface-declaration bound=informational\n" name count) !passes;
    Printf.printf "PASS CHECK definitions=%d\n" (List.length checked.rows); Ok ())
  else if mode = "axioms" then (
    List.iter print_endline (Kanon_surface.Elab.axiom_names checked.rows); Ok ())
  else
    let* () = entry ~budget checked name in
    let* rows = kernel (K.Erase.program ~budget checked.globals checked.rows) in
    if mode = "emit" then emit ~budget ~reactor checked rows name
    else if mode = "run" then
      let* answer, _store = printer (I.run ~budget rows ~entry:name Tether_store.Store.empty) in
      print_endline ("REPLY " ^ reply answer); Ok ()
    else Error (D.Syntax "invalid driver mode")
let () =
  let args = Array.to_list Sys.argv in
  let result = match args with
    | [_program; mode; path; name; fuel] -> run mode path name fuel
    | [] | _ :: _ -> Error (D.Syntax "expected mode, path, entry and fuel") in
  result |> Result.fold ~ok:Fun.id ~error:(fun e -> prerr_endline (D.to_string e);
    exit (match args with _program :: "emit" :: _rest -> 2
      | _program :: "run" :: _rest -> 4 | [] | _ :: _ -> 1))
