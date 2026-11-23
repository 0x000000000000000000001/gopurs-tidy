module Test.Printer (main) where

import Prelude

import Data.Foldable (foldl, for_)
import Data.List (List(..))
import Dodo (Doc, Printer(..))
import Dodo as Dodo
import Effect (Effect)
import Effect.Exception (throw)
import Tidy.Printer as Printer

main :: Effect Unit
main = do
  let
    Printer printer = Printer.plainText :: Printer Printer.Buffer Unit String
    write = printer.writeText 0
    fragments =
      [ []
      , [ "", "" ]
      , [ "ab", "", "cd", "\n", "ef" ]
      , [ "hé", "λ", "😀", "終" ]
      , [ "\xD83D", "\xDE00" ]
      , [ "x\xD83D", "", "\xDE00y" ]
      , [ "\xDE00", "z", "\xD83D" ]
      ]

  for_ fragments \parts -> do
    let buffer = foldl (flip write) printer.emptyBuffer parts
    let expected = foldl append "" parts
    check "fragment order and Unicode" expected (printer.flushBuffer buffer)
    check "repeated flush" expected (printer.flushBuffer buffer)

  let
    base = write "prefix\xD83D" printer.emptyBuffer
    left = write "\xDE00L" base
    right = write "R" base
    extended = write "2" left

  check "shared prefix, left" "prefix😀L" (printer.flushBuffer left)
  check "shared prefix, right" "prefix\xD83DR" (printer.flushBuffer right)
  check "shared prefix, extended" "prefix😀L2" (printer.flushBuffer extended)
  check "shared prefix remains intact" "prefix\xD83D" (printer.flushBuffer base)
  check "empty buffer remains intact" "" (printer.flushBuffer printer.emptyBuffer)

  let
    buffer = write "A" printer.emptyBuffer
    annotated = printer.enterAnnotation unit Nil buffer
    indented = printer.writeIndent 2 "  " (printer.writeBreak annotated)
    completed = write "B" (printer.leaveAnnotation unit Nil indented)

  check "printer callbacks" "A\n  B" (printer.flushBuffer completed)

  for_ [ 4, 12, 80 ] \width -> do
    let opts = Dodo.twoSpaces { pageWidth = width }
    for_ documents \doc ->
      check "same layout as Dodo.plainText"
        (Dodo.print Dodo.plainText opts doc)
        (Dodo.print Printer.plainText opts doc)
  where
  check label expected actual =
    unless (expected == actual) $ throw (label <> ": expected " <> show expected <> ", got " <> show actual)

  documents :: Array (Doc Unit)
  documents =
    [ mempty
    , Dodo.text "héλ😀終"
    , Dodo.annotate unit (Dodo.text "a" <> Dodo.break <> Dodo.indent (Dodo.text "b" <> Dodo.break <> Dodo.text "c"))
    , Dodo.flexGroup (Dodo.paragraph (map Dodo.text [ "alpha", "beta", "gamma" ]))
    , Dodo.text "prefix" <> Dodo.flexSelect (Dodo.paragraph (map Dodo.text [ "one", "two" ])) (Dodo.text "!") (Dodo.break <> Dodo.text "fallback")
    ]
