module D = Tether_surface.Diagnostic
module P = Tether_print
module K = Kanon_kernel
let ( let* ) = Result.bind
let read path =
  print_endline ("READ " ^ path); flush stdout;
  let* header = In_channel.input_line stdin |> Option.to_result ~none:(D.Read path) in
  let* size = int_of_string_opt header |> Option.to_result ~none:(D.Read path) in
  if size < 0 || size > 1048576 then Error (D.Read path) else
  In_channel.really_input_string stdin size |> Option.to_result ~none:(D.Read path)
let kernel result = Result.map_error (fun e -> D.Kernel e) result
let printer result = Result.map_error (fun e -> D.Syntax e) result
let run path entry fuel =
  let* fuel = int_of_string_opt fuel |> Option.to_result ~none:(D.Syntax "invalid fuel") in
  if fuel < 0 then Error (D.Syntax "invalid fuel") else
  let remaining = ref fuel in
  let budget = K.Budget.of_poll (fun () ->
    if !remaining = 0 then true else (decr remaining; false)) in
  let* reactor = read "@reactor" in let* redis = read "@redis" in
  let* checked = Tether_surface.Elab.check ~budget ~read ~path ~reactor ~redis in
  let reply = K.Term.Lan (K.Shape.SMu ("Reply", []), K.Term.Sec (K.Shape.SColl 0, [])) in
  let ty = K.Term.Lan (K.Shape.SMu ("Client", []), K.Term.Sec (K.Shape.SColl 1, [K.Rules.leg_of reply])) in
  let* _checked = kernel (K.Check.check_decls ~budget checked.globals [{ K.Check.d_name = "tetherShEntryCheck";
    d_kind = K.Check.Definition; d_ty = ty; d_body = Some (K.Term.Global entry) }]) in
  let* rows = kernel (K.Erase.program ~budget checked.globals checked.rows) in
  let* plan = printer (P.Sh.plan ~budget rows ~entry) in
  let* artifacts = P.Lua.all (List.map (fun name ->
    let* () = kernel (P.Transport.entry ~budget checked.globals name) in
    let* artifact = printer (P.Lua.emit rows ~entry:name) in
    let* wasm = kernel (P.Transport.wasm ~budget ~reactor artifact) in
    Ok (name, (artifact, wasm))) (List.sort_uniq String.compare plan.invokes)) in
  let* shell = printer (P.Sh.emit plan (List.map (fun (n, (a, _w)) -> n, a) artifacts)) in
  print_endline ("SH " ^ P.Transport.hex shell);
  let finish = match plan.P.Sh.finish with P.Sh.Answer i -> i | P.Sh.Failure -> -1 in
  Printf.printf "CLIENT %d%s\n" finish (String.concat "" (List.map (fun n -> " " ^ n) plan.invokes));
  List.iter (fun (name, (a, wasm)) ->
    Printf.printf "KEYS %s%s\n" name (String.concat "" (List.map (fun key ->
      " " ^ String.concat "" (List.map (Printf.sprintf "%02x") key)) a.P.Lua.keys));
    Printf.printf "ARTIFACT %s %s %s %s\n" name a.P.Lua.sha1
      (P.Transport.hex a.body) (P.Transport.hex wasm)) artifacts;
  Ok ()
let () =
  (match Array.to_list Sys.argv with
   | [_program; path; entry; fuel] -> run path entry fuel
   | [] | _ :: _ -> Error (D.Syntax "expected path, Client entry and fuel"))
  |> Result.fold ~ok:Fun.id ~error:(fun e -> prerr_endline (D.to_string e); exit 2)
