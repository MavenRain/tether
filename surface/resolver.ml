let ( let* ) = Result.bind

(* The host supplies IO as values. Each imported module is read once. *)
let load ~read ~path =
  let rec visit active finished path =
    if List.exists (fun (p, _unit) -> String.equal p path) finished then Ok finished
    else if List.mem path active then Error (Diagnostic.Import_cycle (List.rev (path :: active)))
    else
      let* source = read path in
      let* unit = Parser.parse source in
      let* () = Modpath.check ~path unit.name in
      let* finished = List.fold_left
        (fun acc imported ->
          let* finished = acc in
          let* imported_path = Modpath.file imported in
          visit (path :: active) finished imported_path)
        (Ok finished) unit.imports in
      Ok (finished @ [path, unit]) in
  visit [] [] path |> Result.map (List.map snd)
