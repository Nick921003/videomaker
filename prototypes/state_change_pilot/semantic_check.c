#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void) {
	char name[32];
	strcpy(name, "Alice");
	assert(strlen(name) == 5);
	assert(sizeof name == 32);
	assert(name[5] == '\0');
	printf("%s 共 %d 個字\n", name, (int)strlen(name));
	printf("length=%zu capacity=%zu nul_index=5\n", strlen(name), sizeof name);
	return 0;
}
