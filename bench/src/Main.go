import (
	"fmt"
	"os"
)

func Fixture() string {
	contents, err := os.ReadFile("fixture.purs")
	if err != nil {
		return ""
	}
	return string(contents)
}

func Log(message string) {
	fmt.Println(message)
}
