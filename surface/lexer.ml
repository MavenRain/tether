let lex source =
  Kanon_surface.Lexer.lex source |> Result.map_error (fun e -> Diagnostic.Kernel e)
