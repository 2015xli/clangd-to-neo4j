#compiler = gcc
compiler = clang
versions = -std=c99
object = authenticate.o category.o customer.o decorate.o inventory.o main.o personnel.o pos.o promotion.o purchase.o report.o settings.o support.o systemcall.o transaction.o
exec_file = POS-System

$(exec_file): $(object)
	$(compiler) $(versions) $(object) -o $(exec_file) -lm
	-rm *.o

authenticate.o: authenticate.c main.h
	$(compiler) $(versions) -c authenticate.c

category.o: category.c main.h
	$(compiler) $(versions) -c category.c

customer.o: customer.c main.h
	$(compiler) $(versions) -c customer.c

decorate.o: decorate.c main.h
	$(compiler) $(versions) -c decorate.c

inventory.o: inventory.c main.h
	$(compiler) $(versions) -c inventory.c

main.o: main.c main.h
	$(compiler) $(versions) -c main.c

personnel.o: personnel.c main.h
	$(compiler) $(versions) -c personnel.c

pos.o: sub/pos.c main.h
	$(compiler) $(versions) -c sub/pos.c

promotion.o: promotion.c main.h
	$(compiler) $(versions) -c promotion.c

purchase.o: sub/purchase.c main.h
	$(compiler) $(versions) -c sub/purchase.c

report.o: report.c main.h
	$(compiler) $(versions) -c report.c

settings.o: settings.c main.h
	$(compiler) $(versions) -c settings.c

support.o: support.c main.h
	$(compiler) $(versions) -c support.c

systemcall.o: systemcall.c main.h
	$(compiler) $(versions) -c systemcall.c

transaction.o: transaction.c main.h
	$(compiler) $(versions) -c transaction.c

.PHONY : clean

run:
	./$(exec_file)
