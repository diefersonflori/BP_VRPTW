#include <iostream>

int main(int argc, char* argv[]) {
    std::cout << "HELLO FROM C++" << std::endl;

    if (argc > 1) {
        std::cout << "Args recebidos:" << std::endl;
        for (int i = 1; i < argc; i++) {
            std::cout << "  argv[" << i << "] = " << argv[i] << std::endl;
        }
    }
    return 0;
}
