// Welcome to the program. The declaration of the functions and the library used is in .h file
#include "main.h"

int transactionSelectById (unsigned int id, unsigned int *purchaseId, double *inventoryPrice, double *inventoryProfit,
                           unsigned int *inventoryCategoryId, time_t *timestamp) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.transaction;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( Transaction[i].id == id ) {
            // Return all values back by reference
            *purchaseId = Transaction[i].purchaseId;
            *inventoryPrice = Transaction[i].inventoryPrice;
            *inventoryProfit = Transaction[i].inventoryProfit;
            *inventoryCategoryId = Transaction[i].inventoryCategoryId;
            *timestamp = Transaction[i].timestamp;
            return 1;   // Found a record
        }
    }
    return 0;           // Not found the given `id` in the records
}

void transactionInsert (unsigned int purchaseId, char *inventoryId) {
    int tailIndex = RecordCount.transaction;
    unsigned int trash;    // Don't really want data, just buffer
    Transaction[tailIndex].id = tailIndex;  // Auto-increment
    Transaction[tailIndex].purchaseId = purchaseId;
    strcpy (Transaction[tailIndex].inventoryId, inventoryId);
    inventorySelectById (inventoryId, Transaction[tailIndex].inventoryName, &Transaction[tailIndex].inventoryPrice,
                         &Transaction[tailIndex].inventoryProfit, &Transaction[tailIndex].inventoryCategoryId, &trash);
    Transaction[tailIndex].timestamp = time (NULL);  // Current time as time_t (Epoch format)

    RecordCount.transaction++;    // Update the amount of records

    transactionFileWrite ();       // Save to a Database file
}
