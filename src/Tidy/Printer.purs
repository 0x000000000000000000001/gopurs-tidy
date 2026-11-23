module Tidy.Printer
  ( Buffer
  , plainText
  ) where

import Dodo (Printer(..))

-- | An immutable text buffer. Appending and flushing preserve shared prefixes.
foreign import data Buffer :: Type

foreign import emptyBuffer :: Buffer
foreign import appendText :: String -> Buffer -> Buffer
foreign import flushBuffer :: Buffer -> String

-- | A plain text printer with a buffer suited to each backend. The Go backend
-- | accumulates immutable fragments and assembles the string once at the end.
plainText :: forall a. Printer Buffer a String
plainText = Printer
  { emptyBuffer
  , writeText: \_ text buffer -> appendText text buffer
  , writeIndent: \_ text buffer -> appendText text buffer
  , writeBreak: appendText "\n"
  , enterAnnotation: \_ _ buffer -> buffer
  , leaveAnnotation: \_ _ buffer -> buffer
  , flushBuffer
  }
