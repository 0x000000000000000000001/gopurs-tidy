module Main where

import Prelude

import Dodo as Dodo
import Effect (Effect)
import PureScript.CST (RecoveredParserResult(..), parseModule)
import Tidy (defaultFormatOptions, formatModule, toDoc)
import Tidy.Printer as Printer

foreign import fixture :: Effect String
foreign import log :: String -> Effect Unit
foreign import consume :: String -> Number

iterations :: Int
iterations = 10

formatOnce :: String -> String
formatOnce source =
  case parseModule source of
    ParseSucceeded parsed ->
      Dodo.print Printer.plainText
        { pageWidth: 80
        , ribbonRatio: 1.0
        , indentWidth: 2
        , indentUnit: "  "
        }
        (toDoc (formatModule defaultFormatOptions parsed))
    _ -> ""

main :: Effect Unit
main = do
  source <- fixture
  let
    loop n acc =
      if n <= 0 then acc
      else loop (n - 1) (acc + consume (formatOnce source))
  log (show (loop iterations 0.0))
