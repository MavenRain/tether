module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
(* This walk includes every case arm and closure capture. *)
let children = function
  | E.KVar _ | E.KLit _ | E.KGlobal _ | E.KErased -> []
  | E.KLet (_, a, b) -> [a; b]
  | E.KClos (_, _, xs) | E.KStruct (_, xs) | E.KTag (_, _, xs)
  | E.KDelay (_, xs) -> xs
  | E.KApp (f, xs) | E.KTail (f, xs) -> f :: xs
  | E.KProj (_, _, x) | E.KForce x -> [x]
  | E.KCase (_, x, bs) -> x :: List.map (fun (b : E.kbranch) -> b.body) bs
let reference = function
  | E.KGlobal name | E.KClos (E.Fid name, _, _) | E.KDelay (E.Fid name, _) -> [name]
  | E.KVar _ | E.KLit _ | E.KErased | E.KLet _ | E.KApp _ | E.KTail _
  | E.KStruct _ | E.KProj _ | E.KTag _ | E.KCase _ | E.KForce _ -> []
let rec terms t = t :: List.concat_map terms (children t)
let functions rows = List.concat_map (fun (_name, entry) -> match entry with
  | Kanon_kernel.Erase.Dropped | Kanon_kernel.Erase.Postulate _ -> []
  | Kanon_kernel.Erase.Code ds -> List.filter_map (function
      | E.KFun (E.Fid n, ps, r, b) -> Some (n, (ps, r, b))
      | E.KRec _ -> None) ds) rows

let reachable rows entry =
  let all = functions rows in
  let rec visit seen = function
    | [] -> Ok seen
    | name :: rest ->
        if List.mem_assoc name seen then visit seen rest else
        let* ((_, _, body) as fn) = List.assoc_opt name all
          |> Option.to_result ~none:("LUA-UNSUPPORTED global " ^ name) in
        visit ((name, fn) :: seen) (List.concat_map reference (terms body) @ rest)
  in
  visit [] [entry] |> Result.map (List.sort (fun (a, _) (b, _) -> String.compare a b))

let no_writes functions =
  not (List.exists (fun (_, (_, _, body)) -> List.exists (function
    | E.KTag (E.Tid "mu<Script>", tag, _) -> tag <> 0 && tag <> 2 && tag <> 8
        && tag <> 10 && tag <> 12 && tag <> 13 && tag <> 17 && tag <> 18 && tag <> 23 && tag <> 24 && tag <> 27 && tag <> 28 && tag <> 29 && tag <> 30 && tag <> 31 && tag <> 32 && tag <> 33 && tag <> 34 && tag <> 41 && tag <> 42 && tag <> 46 && tag <> 47 && tag <> 52
    | E.KVar _ | E.KLit _ | E.KGlobal _ | E.KErased | E.KLet _ | E.KClos _
    | E.KApp _ | E.KTail _ | E.KStruct _ | E.KProj _ | E.KTag _ | E.KCase _
    | E.KDelay _ | E.KForce _ -> false) (terms body)) functions)
