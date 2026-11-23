import (
	"fmt"
	"os"
)

func Fixture() string {
	contents, err := os.ReadFile("fixture.purs")
	if err != nil {
		panic(err)
	}
	return string(contents)
}

func Log(message string) {
	fmt.Println(message)
}

// Read the same UTF-8 bytes as the JavaScript Buffer consumer.
func Consume(text string) float64 {
	hash := uint32(2166136261)
	for i := 0; i < len(text); i++ {
		hash = (hash ^ uint32(text[i])) * 16777619
	}
	return float64(hash)
}
