module Main where

import Prelude

import Data.String.CodeUnits as SCU
import Dodo as Dodo
import Effect (Effect)
import PureScript.CST (RecoveredParserResult(..), parseModule)
import Tidy (defaultFormatOptions, formatModule, toDoc)

foreign import fixture :: Effect String
foreign import log :: String -> Effect Unit

iterations :: Int
iterations = 10

formatOnce :: String -> String
formatOnce source =
  case parseModule source of
    ParseSucceeded parsed ->
      Dodo.print Dodo.plainText
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
      else loop (n - 1) (acc + SCU.length (formatOnce source))
  log (show (loop iterations 0))
