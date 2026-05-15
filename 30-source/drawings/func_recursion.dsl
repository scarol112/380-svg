# func_recursion.dsl — factorial(6) == 720

def factorial(n) {
    if ($n <= 1) {
        return 1
    }
    return (n * factorial((n - 1)))
}

numeric result = factorial(6)
lb 0.5,1 14 "factorial(6) should be 720"
vardump
