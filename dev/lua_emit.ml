module D = Tether_surface.Diagnostic
module P = Tether_print
let ( let* ) = Result.bind
let read path =
  print_endline ("READ " ^ path); flush stdout;
  let* header = In_channel.input_line stdin |> Option.to_result ~none:(D.Read path) in
  let* size = int_of_string_opt header |> Option.to_result ~none:(D.Read path) in
  if size < 0 || size > 1048576 then Error (D.Read path) else
  In_channel.really_input_string stdin size |> Option.to_result ~none:(D.Read path)
let kernel result = Result.map_error (fun e -> D.Kernel e) result
let run path entry fuel =
  let* remaining = int_of_string_opt fuel |> Option.to_result ~none:(D.Syntax "invalid fuel") in
  if remaining < 0 then Error (D.Syntax "invalid fuel") else
  let remaining = ref remaining in
  let budget = Kanon_kernel.Budget.of_poll (fun () ->
    if !remaining = 0 then true else (decr remaining; false)) in
  let* reactor = read "@reactor" in let* redis = read "@redis" in
  let* checked = Tether_surface.Elab.check ~budget ~read ~path ~reactor ~redis in
  let* () = kernel (P.Transport.entry ~budget checked.globals entry) in
  let* rows = kernel (Kanon_kernel.Erase.program ~budget checked.globals checked.rows) in
  let* artifact = P.Lua.emit rows ~entry |> Result.map_error (fun e -> D.Syntax e) in
  let* wasm = kernel (P.Transport.wasm ~budget ~reactor artifact) in
  print_endline ("LUA " ^ P.Transport.hex artifact.body);
  print_endline ("WASM " ^ P.Transport.hex wasm);
  print_endline ("SHA1 " ^ artifact.sha1);
  List.iter (fun key -> print_endline ("KEY " ^ String.concat ""
    (List.map (Printf.sprintf "%02x") key))) artifact.keys;
  Printf.printf "FLAGS no-writes=%d\n" (if artifact.no_writes then 1 else 0);
  Ok ()
let () =
  (match Array.to_list Sys.argv with
   | [_program; path; entry; fuel] -> run path entry fuel
   | [] | _ :: _ -> Error (D.Syntax "expected path, Script entry and fuel"))
  |> Result.fold ~ok:Fun.id ~error:(fun e -> prerr_endline (D.to_string e); exit 2)
