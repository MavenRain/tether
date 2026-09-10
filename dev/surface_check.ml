module D = Tether_surface.Diagnostic
let ( let* ) = Result.bind

(* Length-prefixed host responses preserve arbitrary source bytes. *)
let read path =
  print_endline ("READ " ^ path);
  flush stdout;
  let* header = In_channel.input_line stdin
    |> Option.to_result ~none:(D.Read ("host disconnected: " ^ path)) in
  let* length = int_of_string_opt header
    |> Option.to_result ~none:(D.Read path) in
  if length < 0 then Error (D.Read path)
  else if length > 1048576 then Error (D.Read ("source size: " ^ path))
  else In_channel.really_input_string stdin length
    |> Option.to_result ~none:(D.Read ("short source: " ^ path))

let run ~budget path =
  let* reactor = read "@reactor" in
  let* redis = read "@redis" in
  Tether_surface.Elab.check ~budget ~read ~path ~reactor ~redis

let erased ~budget checked =
  Kanon_kernel.Erase.program ~budget checked.Tether_surface.Elab.globals checked.rows
  |> Result.map_error (fun e -> D.Kernel e)
  |> Result.map (fun rows ->
      List.iter (fun (name, entry) -> match entry with
        | Kanon_kernel.Erase.Dropped -> ()
        | Kanon_kernel.Erase.Postulate _repr -> print_endline ("AXIOM " ^ name)
        | Kanon_kernel.Erase.Code decls ->
            List.iter (fun decl -> print_endline (Kanon_kernel.Eterm.print_decl decl)) decls) rows)

let () =
  let output = match Array.to_list Sys.argv with
    | [_program; path; fuel; mode] ->
        let* fuel = int_of_string_opt fuel |> Option.to_result ~none:(D.Syntax "invalid fuel") in
        if fuel < 0 then Error (D.Syntax "fuel must be nonnegative") else
        let remaining = ref fuel in
        let budget = Kanon_kernel.Budget.of_poll (fun () ->
          if !remaining = 0 then true else (decr remaining; false)) in
        let* checked = run ~budget path in
        let* () = if String.equal mode "erased" then erased ~budget checked
          else if String.equal mode "check" then Ok () else Error (D.Syntax "invalid mode") in
        Ok checked
    | args -> Error (D.Syntax ("expected entry path, arguments=" ^ string_of_int (List.length args))) in
  output |> Result.fold
    ~ok:(fun checked -> Printf.printf "PASS SURFACE definitions=%d schemas=%d\n"
      (List.length checked.Tether_surface.Elab.rows) (List.length checked.schemas))
    ~error:(fun error -> prerr_endline (D.to_string error); exit 1)
