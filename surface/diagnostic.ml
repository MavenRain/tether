type t =
  | Syntax of string
  | Module_path of string
  | Import_cycle of string list
  | Read of string
  | Schema of string
  | Wrongtype of string
  | Int64 of string
  | Reserved of string
  | Duplicate of string
  | Kernel of Kanon_kernel.Error.t

let to_string = function
  | Syntax s -> "SYNTAX " ^ s
  | Module_path s -> "MODULE-PATH " ^ s
  | Import_cycle names -> "IMPORT-CYCLE " ^ String.concat " -> " names
  | Read s -> "READ " ^ s
  | Schema s -> "SLOT-STATIC " ^ s
  | Wrongtype s -> "WRONGTYPE " ^ s
  | Int64 s -> "INT64 " ^ s
  | Reserved s -> "RESERVED " ^ s
  | Duplicate s -> "DUPLICATE " ^ s
  | Kernel e -> "CHECK " ^ Kanon_kernel.Error.to_string e
