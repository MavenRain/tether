let segment s =
  match List.of_seq (String.to_seq s) with
  | [] -> false
  | c :: cs ->
      c >= 'A' && c <= 'Z'
      && List.for_all
           (fun c -> (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')
                     || (c >= '0' && c <= '9')) cs

let validate name =
  if List.for_all segment (String.split_on_char '.' name) then Ok name
  else Error (Diagnostic.Module_path ("expected dotted PascalCase: " ^ name))

let file name =
  Result.map
    (fun name -> String.concat "/" (String.split_on_char '.' name) ^ ".tet")
    (validate name)

let check ~path name =
  Result.bind (file name) (fun expected ->
    if String.equal path expected then Ok ()
    else Error (Diagnostic.Module_path (name ^ " must live at " ^ expected ^ ", got " ^ path)))
