import "gopurs/output/gopurs_runtime"

// TextBuffer is persistent: appending to a prefix never changes another branch
// of a layout, and a buffer can be flushed more than once.
type TextBuffer struct {
	previous *TextBuffer
	text     string
	count    int
}

var EmptyBuffer *TextBuffer

func AppendText(text string, buffer *TextBuffer) *TextBuffer {
	if text == "" {
		return buffer
	}
	count := 1
	if buffer != nil {
		count += buffer.count
	}
	return &TextBuffer{previous: buffer, text: text, count: count}
}

func FlushBuffer(buffer *TextBuffer) string {
	if buffer == nil {
		return ""
	}
	parts := make([]string, buffer.count)
	for node, i := buffer, buffer.count-1; node != nil; node, i = node.previous, i-1 {
		parts[i] = node.text
	}
	// Preserve PureScript string concatenation, including surrogate pairs split
	// between fragments. Joining the raw Go bytes would leave such pairs split.
	return gopurs_runtime.ConcatStrings("", parts, func(text string) string { return text })
}
