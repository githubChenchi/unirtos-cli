#include "include.h"

//QOSA core definition header
#include "qosa_def.h"
//Include QOSA system API header
#include "qosa_sys.h"
//Include QOSA log system header file
#include "qosa_log.h"

//Define log information
#define QOS_LOG_TAG   LOG_TAG_DEMO

#include "unirtos_app_init_registry.h"

//Define stack size of hello world task as 1024 bytes
#define UNIR_HELLO_WORLD_DEMO_TASK_STACK_SIZE 1024
//Define hello world task priority as normal
#define UNIR_HELLO_WORLD_DEMO_TASK_PRIO QOSA_PRIORITY_NORMAL

//Declare global task handle and initialize as NULL
static qosa_task_t g_unir_hello_world_demo_task = QOSA_NULL;

//Define the main process function for the hello world task
static void unir_hello_world_demo_process(void *ctx)
{
    //Initialize counter
    int hello_world_cnt = 0;

    //Infinite loop
    while (1)
    {
        //Print verbose log showing the current count value
        QLOGV("hello world count=%d", hello_world_cnt++);
        //Task sleeps for 1000 ms (1 second)
        qosa_task_sleep_ms(1000);
    }
}

//Initialization function for the hello world demo
void unir_hello_world_init(void)
{
    //Print verbose log indicating entry into hello world demo
    QLOGV("enter hello world demo !!!");
    //Check if the task has not been created yet
    if (g_unir_hello_world_demo_task == QOSA_NULL)
    {
        //Create hello world task
        qosa_task_create(
            &g_unir_hello_world_demo_task,                //Task handle pointer
            UNIR_HELLO_WORLD_DEMO_TASK_STACK_SIZE,        //Task stack size
            UNIR_HELLO_WORLD_DEMO_TASK_PRIO,              //Task priority
            "unir_hello_world_demo",                      //Task name
            unir_hello_world_demo_process,                //Task handler
            QOSA_NULL);                                   //Task parameter
    }
}
UNIRTOS_APP_EXPORT(700, "unir_hello_world_demo", unir_hello_world_init);